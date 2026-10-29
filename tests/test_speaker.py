import numpy as np
import pytest

from speaker import MIN_EMBED_S, SAMPLE_RATE, SpeakerLabeler, SpeakerTracker
from vad import Segment


def seg(source, seconds):
    return Segment(source, np.zeros(int(seconds * SAMPLE_RATE), dtype=np.float32), 0.0, 0.0, 0.0, False)


def unit(*v):
    v = np.array(v, dtype=float)
    return v / np.linalg.norm(v)


def at_similarity(sim):
    """A unit vector whose cosine similarity to (1, 0, 0) is `sim`."""
    return np.array([sim, np.sqrt(1 - sim ** 2), 0.0])


def labeler_with(embeddings):
    it = iter(embeddings)
    return SpeakerLabeler(lambda samples: next(it), SpeakerTracker(match_threshold=0.6, new_threshold=0.4))


def test_mic_is_always_me_without_embedding():
    lab = SpeakerLabeler(lambda samples: pytest.fail("mic audio must not be embedded"))
    assert lab.label(seg("mic", 3.0)).label == "ME"
    assert lab.label(seg("mic", 0.2)).label == "ME"


def test_short_loopback_segment_is_unknown_without_embedding():
    lab = SpeakerLabeler(lambda samples: pytest.fail("short audio must not be embedded"))
    out = lab.label(seg("loopback", MIN_EMBED_S - 0.01))
    assert out.label == "SPEAKER ?" and out.similarity is None


def test_first_remote_voice_is_speaker_1():
    out = labeler_with([unit(1, 0, 0)]).label(seg("loopback", 2.0))
    assert out.label == "SPEAKER 1" and out.similarity is None


def test_match_new_and_uncertain():
    # The last one is off-plane so it stays about 0.5 from the moved SPEAKER 1 centroid and far from SPEAKER 2.
    lab = labeler_with([unit(1, 0, 0), at_similarity(0.9), at_similarity(0.1), unit(0.5, 0, np.sqrt(0.75))])
    labels = [lab.label(seg("loopback", 2.0)) for _ in range(4)]
    assert [x.label for x in labels] == ["SPEAKER 1", "SPEAKER 1", "SPEAKER 2", "SPEAKER ?"]
    assert labels[1].similarity == pytest.approx(0.9, abs=1e-6)
    assert lab.speakers == 2


def test_thresholds_are_inclusive_for_match_only():
    tracker = SpeakerTracker(match_threshold=0.6, new_threshold=0.4)
    tracker.assign(unit(1, 0, 0))
    assert tracker.assign(at_similarity(0.6)).label == "SPEAKER 1"
    tracker = SpeakerTracker(match_threshold=0.6, new_threshold=0.4)
    tracker.assign(unit(1, 0, 0))
    assert tracker.assign(at_similarity(0.4)).label == "SPEAKER ?"


def test_numbering_follows_first_appearance_and_matches_best_speaker():
    tracker = SpeakerTracker(match_threshold=0.6, new_threshold=0.4)
    a, b, c = unit(1, 0, 0), unit(0, 1, 0), unit(0, 0, 1)
    assert [tracker.assign(v).label for v in (a, b, c)] == ["SPEAKER 1", "SPEAKER 2", "SPEAKER 3"]
    assert tracker.assign(unit(0.1, 1, 0)).label == "SPEAKER 2"
    assert tracker.assign(unit(0, 0.1, 1)).label == "SPEAKER 3"


def test_uncertain_segment_does_not_move_centroid():
    tracker = SpeakerTracker(match_threshold=0.6, new_threshold=0.4)
    tracker.assign(unit(1, 0, 0))
    before = tracker.sums[0].copy()
    assert tracker.assign(at_similarity(0.5)).label == "SPEAKER ?"
    np.testing.assert_array_equal(tracker.sums[0], before)


def test_centroid_is_scale_invariant():
    tracker = SpeakerTracker()
    tracker.assign(np.array([3.0, 0, 0]))
    out = tracker.assign(np.array([0.01, 0, 0]))
    assert out.label == "SPEAKER 1" and out.similarity == pytest.approx(1.0)


def test_zero_embedding_and_bad_thresholds_fail_loudly():
    with pytest.raises(ValueError, match="all zeros"):
        SpeakerTracker().assign(np.zeros(3))
    with pytest.raises(ValueError, match="above MATCH_THRESHOLD"):
        SpeakerTracker(match_threshold=0.3, new_threshold=0.5)


@pytest.mark.slow
def test_titanet_embedding_shape_and_self_similarity():
    """Real TitaNet: same clip twice -> similarity ~1; uses the recorded clips when present."""
    import torch
    from pathlib import Path

    from speaker import Embedder

    device = "cuda" if torch.cuda.is_available() else "cpu"
    embed = Embedder(device)
    clip = Path(__file__).parent.parent / "bench" / "clips" / "hakob" / "09.wav"
    if clip.exists():
        import soundfile as sf
        samples, rate = sf.read(clip, dtype="float32")
        assert rate == SAMPLE_RATE
    else:
        samples = (0.1 * np.random.default_rng(0).standard_normal(3 * SAMPLE_RATE)).astype(np.float32)
    e1, e2 = embed(samples), embed(samples.copy())
    assert e1.shape == (192,)
    tracker = SpeakerTracker()
    tracker.assign(e1)
    assert tracker.assign(e2).similarity > 0.99
