"""Voice activity detection: cut one source's 16 kHz chunk stream into speech segments with Silero VAD.

Each source gets its own Segmenter, and its own Silero model, because the model keeps state between
chunks. Segments end at a pause (300 ms of silence) or are cut at MAX_SEGMENT_S so long speech never
blows the latency budget. A forced cut is placed at the quietest 50 ms in the last CUT_SEARCH_S of the
segment (usually a breath or a gap between words), not at the exact 5 s mark, so words are not split;
the audio after the cut starts the next segment.

A segment shorter than SHORT_S that ends at a pause is held back instead of sent: if speech starts again
within HOLD_S it is joined to that speech (gap included), so short Armenian words stay with their sentence;
if nothing follows, it is dropped. Alone, such fragments are usually a noise, a breath or a cough, and the
ASR turns them into words ("Հովհ.") that NLLB then translates ("John: I know.").
"""

import time
from dataclasses import dataclass

import numpy as np

from audio_capture import SAMPLE_RATE

MAX_SEGMENT_S = 5.0
PRE_ROLL_S = 1.0  # audio kept before speech start so the VAD start index stays reachable
MIN_SILENCE_MS = 300
SPEECH_PAD_MS = 100
CUT_SEARCH_S = 2.0  # a forced cut looks this far back for the quietest point
CUT_FRAME = 800  # 50 ms at 16 kHz: energy is compared per frame
SHORT_S = 0.5  # a segment shorter than this is only kept if more speech follows...
HOLD_S = 1.0  # ...within this long after it ends


@dataclass
class Segment:
    source: str  # "mic" or "loopback"
    samples: np.ndarray  # 16 kHz mono float32
    t_speech_end: float  # wall time of the last speech sample
    t_closing_chunk: float  # wall time the chunk that closed the segment was captured
    t_vad_done: float
    forced_cut: bool  # True when cut at MAX_SEGMENT_S instead of at a pause


def silero_detector():
    """A fresh Silero VADIterator, as a function chunk -> event dict ({"start": i} / {"end": i}) or None."""
    import torch
    from silero_vad import VADIterator, load_silero_vad

    vad = VADIterator(load_silero_vad(), sampling_rate=SAMPLE_RATE, min_silence_duration_ms=MIN_SILENCE_MS,
                      speech_pad_ms=SPEECH_PAD_MS)
    return lambda chunk: vad(torch.from_numpy(chunk))


class Segmenter:
    """Feed AudioChunks of one source in order; returns a Segment when one is finished, else None.

    `detect` returns Silero-style events whose indices count samples from the start of the stream.
    """

    def __init__(self, source, detect):
        self.source = source
        self.detect = detect
        self.buffer = np.zeros(0, dtype=np.float32)
        self.buffer_start = 0  # stream sample index of buffer[0]
        self.speech_start = None  # stream sample index where current speech began
        self.held = None  # (start, end) of a short segment waiting for more speech, see SHORT_S
        self.dropped = 0  # short segments dropped because nothing followed
        self.after_cut = False  # current speech continues a forced cut: its tail is never held or dropped

    def feed(self, chunk):
        if chunk.source != self.source:
            raise ValueError(f"{self.source} segmenter got a {chunk.source} chunk")
        self.buffer = np.concatenate([self.buffer, chunk.samples])
        event = self.detect(chunk.samples)
        stream_pos = self.buffer_start + len(self.buffer)

        if event and "start" in event:
            self.speech_start = event["start"]
            self.after_cut = False
            if self.held is not None:
                self.speech_start = self.held[0]  # more speech came: join the held fragment to it
                self.held = None
        if self.held is not None and stream_pos - self.held[1] >= HOLD_S * SAMPLE_RATE:
            self.held = None  # nothing followed: drop it
            self.dropped += 1

        end = None
        forced = False
        if event and "end" in event and self.speech_start is not None:
            end = event["end"]
        elif self.speech_start is not None and stream_pos - self.speech_start >= MAX_SEGMENT_S * SAMPLE_RATE:
            end = self._quietest_point(stream_pos)
            forced = True

        segment = None
        if end is not None and end <= self.speech_start:
            # VAD closed the speech right after a forced cut: nothing left to emit.
            self.speech_start = None
            self.after_cut = False
        elif end is not None and not forced and not self.after_cut and end - self.speech_start < SHORT_S * SAMPLE_RATE:
            self.held = (self.speech_start, end)
            self.speech_start = None
        elif end is not None:
            segment = Segment(
                source=self.source,
                samples=self.buffer[max(self.speech_start - self.buffer_start, 0):end - self.buffer_start],
                t_speech_end=chunk.t_captured - (stream_pos - end) / SAMPLE_RATE,
                t_closing_chunk=chunk.t_captured,
                t_vad_done=time.time(),
                forced_cut=forced,
            )
            # A forced cut keeps the VAD in speech state; the next segment starts here.
            self.speech_start = end if forced else None
            self.after_cut = forced

        # Drop audio that can no longer be part of a segment.
        if self.speech_start is not None:
            keep_from = self.speech_start
        elif self.held is not None:
            keep_from = self.held[0]
        else:
            keep_from = stream_pos - int(PRE_ROLL_S * SAMPLE_RATE)
        if keep_from > self.buffer_start:
            self.buffer = self.buffer[keep_from - self.buffer_start:]
            self.buffer_start = keep_from
        return segment

    def _quietest_point(self, stream_pos):
        """Stream index at the centre of the lowest-energy frame in the last CUT_SEARCH_S of the buffer."""
        lo = max(self.speech_start, self.buffer_start, stream_pos - int(CUT_SEARCH_S * SAMPLE_RATE))
        audio = self.buffer[lo - self.buffer_start:stream_pos - self.buffer_start]
        n = len(audio) // CUT_FRAME
        if n == 0:
            return stream_pos
        energy = np.square(audio[len(audio) - n * CUT_FRAME:].reshape(n, CUT_FRAME)).mean(axis=1)
        quietest = int(np.argmin(energy[::-1]))  # ties go to the latest frame, keeping segments long
        return stream_pos - quietest * CUT_FRAME - CUT_FRAME // 2
