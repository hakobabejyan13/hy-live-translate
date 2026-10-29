"""Segmenter bookkeeping with a scripted detector in place of Silero (no model, no audio device)."""

import numpy as np
import pytest

from audio_capture import CHUNK, SAMPLE_RATE, AudioChunk
from vad import MAX_SEGMENT_S, Segmenter


def run(events, n_chunks, source="loopback", t0=1000.0):
    """events: {chunk index: event dict}. Chunk i holds the value i, so segment contents are checkable."""
    calls = iter(range(n_chunks))
    seg = Segmenter(source, lambda samples: events.get(next(calls)))
    out = []
    for i in range(n_chunks):
        chunk = AudioChunk(source, np.full(CHUNK, i, dtype=np.float32), t0 + (i + 1) * CHUNK / SAMPLE_RATE)
        s = seg.feed(chunk)
        if s is not None:
            out.append((i, s))
    return out


def test_segment_cut_at_pause_has_exact_samples_and_times():
    start, end = 10 * CHUNK + 100, 30 * CHUNK + 7
    segs = run({10: {"start": start}, 40: {"end": end}}, 50)
    assert len(segs) == 1
    i, s = segs[0]
    assert i == 40 and s.source == "loopback" and not s.forced_cut
    assert len(s.samples) == end - start
    assert s.samples[0] == 10 and s.samples[-1] == 30  # from the chunks that held start and end
    t_closing = 1000.0 + 41 * CHUNK / SAMPLE_RATE
    assert s.t_closing_chunk == t_closing
    assert s.t_speech_end == pytest.approx(1000.0 + end / SAMPLE_RATE)


def test_long_speech_is_cut_at_max_length_and_continues():
    max_samples = int(MAX_SEGMENT_S * SAMPLE_RATE)
    n = 2 * max_samples // CHUNK + 20
    end = (n - 2) * CHUNK
    segs = run({0: {"start": 0}, n - 1: {"end": end}}, n)
    forced = [s for _, s in segs if s.forced_cut]
    assert len(forced) == 2
    assert all(len(s.samples) >= max_samples and len(s.samples) < max_samples + CHUNK for s in forced)
    last = segs[-1][1]
    assert not last.forced_cut
    assert sum(len(s.samples) for _, s in segs) == end  # no audio lost or doubled across cuts


def test_end_right_after_forced_cut_emits_nothing_more():
    cut_chunk = -(-int(MAX_SEGMENT_S * SAMPLE_RATE) // CHUNK) - 1  # first chunk that reaches the max length
    cut_pos = (cut_chunk + 1) * CHUNK
    segs = run({0: {"start": 0}, cut_chunk + 1: {"end": cut_pos}}, cut_chunk + 5)
    assert [s.forced_cut for _, s in segs] == [True]


def test_buffer_does_not_grow_in_silence():
    seg = Segmenter("mic", lambda samples: None)
    for i in range(2000):
        seg.feed(AudioChunk("mic", np.zeros(CHUNK, dtype=np.float32), float(i)))
    assert len(seg.buffer) <= SAMPLE_RATE + CHUNK


def test_chunk_from_other_source_fails_loudly():
    seg = Segmenter("mic", lambda samples: None)
    with pytest.raises(ValueError, match="mic segmenter got a loopback chunk"):
        seg.feed(AudioChunk("loopback", np.zeros(CHUNK, dtype=np.float32), 0.0))
