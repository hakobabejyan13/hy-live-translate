"""Segmenter bookkeeping with a scripted detector in place of Silero (no model, no audio device)."""

import numpy as np
import pytest

from audio_capture import CHUNK, SAMPLE_RATE, AudioChunk
from vad import CUT_FRAME, CUT_SEARCH_S, MAX_SEGMENT_S, Segmenter


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
    min_samples = max_samples - CUT_SEARCH_S * SAMPLE_RATE
    assert all(min_samples <= len(s.samples) < max_samples + CHUNK for s in forced)
    last = segs[-1][1]
    assert not last.forced_cut
    assert sum(len(s.samples) for _, s in segs) == end  # no audio lost or doubled across cuts


def test_forced_cut_lands_in_the_quiet_gap_not_mid_word():
    """Loud speech with one quiet 0.1 s gap at ~4 s: the 5 s cut goes into the gap, the rest starts the next segment."""
    gap = int(4.0 * SAMPLE_RATE)
    calls = iter(range(10_000))
    seg = Segmenter("mic", lambda samples: {"start": 0} if next(calls) == 0 else None)
    out = []
    for i in range(int(MAX_SEGMENT_S * SAMPLE_RATE) // CHUNK + 2):
        pos = np.arange(i * CHUNK, (i + 1) * CHUNK)
        samples = np.where((pos >= gap) & (pos < gap + 1600), 0.001, 0.5).astype(np.float32)
        s = seg.feed(AudioChunk("mic", samples, float(i)))
        if s is not None:
            out.append(s)
    assert len(out) == 1 and out[0].forced_cut
    assert gap <= len(out[0].samples) <= gap + 1600
    assert np.all(out[0].samples[:gap] == 0.5)
    assert seg.speech_start == len(out[0].samples)  # next segment continues right after the cut


def test_end_right_after_forced_cut_emits_nothing_more():
    cut_chunk = -(-int(MAX_SEGMENT_S * SAMPLE_RATE) // CHUNK) - 1  # first chunk that reaches the max length
    # Constant-level audio: every frame ties, so the cut lands in the last 50 ms frame; VAD then ends before it.
    calls = iter(range(10_000))
    events = {0: {"start": 0}, cut_chunk + 1: {"end": (cut_chunk + 1) * CHUNK - CUT_FRAME}}
    seg = Segmenter("loopback", lambda samples: events.get(next(calls)))
    segs = []
    for i in range(cut_chunk + 5):
        s = seg.feed(AudioChunk("loopback", np.full(CHUNK, 0.5, dtype=np.float32), float(i)))
        if s is not None:
            segs.append((i, s))
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


def test_short_fragment_followed_by_speech_is_joined_to_it():
    short_end = 10 * CHUNK + int(0.3 * SAMPLE_RATE)  # 0.3 s fragment
    nxt = short_end + int(0.5 * SAMPLE_RATE)  # speech again 0.5 s later
    end = nxt + 2 * SAMPLE_RATE
    segs = run({10: {"start": 10 * CHUNK}, 25: {"end": short_end}, 40: {"start": nxt}, 120: {"end": end}}, 130)
    assert len(segs) == 1
    s = segs[0][1]
    assert len(s.samples) == end - 10 * CHUNK and s.samples[0] == 10  # fragment, gap and speech in one segment


def test_short_fragment_with_nothing_after_is_dropped():
    calls = iter(range(10_000))
    events = {10: {"start": 10 * CHUNK}, 25: {"end": 10 * CHUNK + int(0.3 * SAMPLE_RATE)}}
    seg = Segmenter("loopback", lambda samples: events.get(next(calls)))
    out = [seg.feed(AudioChunk("loopback", np.full(CHUNK, i, dtype=np.float32), float(i))) for i in range(200)]
    assert all(s is None for s in out)
    assert seg.dropped == 1 and seg.held is None
    assert len(seg.buffer) <= SAMPLE_RATE + CHUNK


def test_short_tail_after_forced_cut_is_kept():
    cut_chunk = -(-int(MAX_SEGMENT_S * SAMPLE_RATE) // CHUNK) - 1
    end = (cut_chunk + 1) * CHUNK + int(0.2 * SAMPLE_RATE)  # speech ends 0.2 s after the max length
    calls = iter(range(10_000))
    events = {0: {"start": 0}, cut_chunk + 8: {"end": end}}
    seg = Segmenter("loopback", lambda samples: events.get(next(calls)))
    segs = []
    for i in range(cut_chunk + 20):
        s = seg.feed(AudioChunk("loopback", np.full(CHUNK, 0.5, dtype=np.float32), float(i)))
        if s is not None:
            segs.append(s)
    assert [s.forced_cut for s in segs] == [True, False]
    assert sum(len(s.samples) for s in segs) == end
