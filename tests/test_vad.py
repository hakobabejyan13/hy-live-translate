"""Segmenter bookkeeping with a scripted detector in place of Silero (no model, no audio device)."""

import numpy as np
import pytest

from audio_capture import CHUNK, SAMPLE_RATE, AudioChunk
from vad import CUT_SEARCH_S, HARD_MAX_S, MAX_SEGMENT_S, PAUSE_S, Segmenter


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


def test_long_speech_without_pauses_is_cut_at_hard_max_and_continues():
    hard = int(HARD_MAX_S * SAMPLE_RATE)
    n = 2 * hard // CHUNK + 20
    end = (n - 2) * CHUNK
    segs = run({0: {"start": 0}, n - 1: {"end": end}}, n)  # rising level: never a pause
    forced = [s for _, s in segs if s.forced_cut]
    assert len(forced) == 2
    min_samples = hard - CUT_SEARCH_S * SAMPLE_RATE
    assert all(min_samples <= len(s.samples) < hard + CHUNK for s in forced)
    last = segs[-1][1]
    assert not last.forced_cut
    assert sum(len(s.samples) for _, s in segs) == end  # no audio lost or doubled across cuts


def speech_with_quiet(quiet, n_chunks):
    """Loud speech from the stream start, quiet (0.001) in the [start, end) sample ranges of `quiet`.
    Returns [(chunk index, Segment)] and the Segmenter."""
    calls = iter(range(100_000))
    seg = Segmenter("mic", lambda samples: {"start": 0} if next(calls) == 0 else None)
    out = []
    for i in range(n_chunks):
        pos = np.arange(i * CHUNK, (i + 1) * CHUNK)
        quiet_here = np.zeros(CHUNK, dtype=bool)
        for a, b in quiet:
            quiet_here |= (pos >= a) & (pos < b)
        s = seg.feed(AudioChunk("mic", np.where(quiet_here, 0.001, 0.5).astype(np.float32), float(i)))
        if s is not None:
            out.append((i, s))
    return out, seg


def chunk_at(seconds):
    return int(seconds * SAMPLE_RATE) // CHUNK


def test_forced_cut_lands_in_the_pause_between_words():
    """A 0.2 s gap at 4 s: at 5 s the cut goes into the gap, the rest starts the next segment."""
    gap = int(4.0 * SAMPLE_RATE)
    out, seg = speech_with_quiet([(gap, gap + 3200)], chunk_at(MAX_SEGMENT_S) + 2)
    assert len(out) == 1 and out[0][1].forced_cut
    s = out[0][1]
    assert gap <= len(s.samples) <= gap + 3200
    assert np.all(s.samples[:gap] == 0.5)
    assert seg.speech_start == len(s.samples)  # next segment continues right after the cut


def test_consonant_closure_is_not_a_cut_point():
    """The 2026-10-31 split "հանդիպ|ման": a 60 ms closure inside a word at 4 s is skipped; the segment waits
    for the 0.2 s pause at 5.6 s and is cut there."""
    closure, pause = int(4.0 * SAMPLE_RATE), int(5.6 * SAMPLE_RATE)
    out, _ = speech_with_quiet([(closure, closure + 960), (pause, pause + 3200)], chunk_at(HARD_MAX_S) + 2)
    assert len(out) == 1
    i, s = out[0]
    assert s.forced_cut and pause <= len(s.samples) <= pause + 3200
    assert i < chunk_at(6.0)  # cut as soon as the pause is heard, not at the hard limit


def test_no_pause_means_cut_at_hard_max_in_the_quietest_spot():
    closure = int(5.5 * SAMPLE_RATE)
    out, _ = speech_with_quiet([(closure, closure + 960)], chunk_at(HARD_MAX_S) + 2)
    assert len(out) == 1
    i, s = out[0]
    assert s.forced_cut and i == -(-int(HARD_MAX_S * SAMPLE_RATE) // CHUNK) - 1  # first chunk at the hard limit
    assert closure <= len(s.samples) <= closure + 960 + int(PAUSE_S * SAMPLE_RATE)


def test_cut_stays_within_the_latency_budget():
    """Even waiting for a pause, the cut is never more than CUT_SEARCH_S behind the newest audio."""
    for quiet in ([], [(int(3.2 * SAMPLE_RATE), int(3.5 * SAMPLE_RATE))]):
        out, _ = speech_with_quiet(quiet, chunk_at(HARD_MAX_S) + 2)
        for i, s in out:
            assert (i + 1) * CHUNK - len(s.samples) <= CUT_SEARCH_S * SAMPLE_RATE


def test_end_right_after_forced_cut_emits_nothing_more():
    cut_chunk = -(-int(HARD_MAX_S * SAMPLE_RATE) // CHUNK) - 1  # first chunk that reaches the hard limit
    # Constant-level audio: no pause, every window ties, so the cut lands in the last window; VAD then ends before it.
    calls = iter(range(10_000))
    events = {0: {"start": 0}, cut_chunk + 1: {"end": (cut_chunk + 1) * CHUNK - int(PAUSE_S * SAMPLE_RATE)}}
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
    cut_chunk = -(-int(HARD_MAX_S * SAMPLE_RATE) // CHUNK) - 1
    end = (cut_chunk + 1) * CHUNK + int(0.2 * SAMPLE_RATE)  # speech ends 0.2 s after the hard limit
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
