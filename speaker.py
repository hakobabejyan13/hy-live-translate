"""Speaker labels: mic is always ME; remote speakers on the loopback are SPEAKER 1, 2, ... or SPEAKER ?.

Loopback segments get a speaker embedding (NVIDIA TitaNet-Large via NeMo, already installed for ASR),
compared by cosine similarity to the centroids of the speakers seen so far in this session:
  similarity >= MATCH_THRESHOLD           -> that speaker, centroid updated
  similarity <  NEW_THRESHOLD, or no one  -> new SPEAKER N+1
  anything in between                     -> SPEAKER ? (uncertain, not guessed)
Segments shorter than MIN_EMBED_S are SPEAKER ? without matching: embeddings of short audio are unreliable.
Thresholds are starting values to tune on live calls; the best similarity is logged per line for that.
"""

from dataclasses import dataclass

import numpy as np

SPEAKER_MODEL = "nvidia/speakerverification_en_titanet_large"
SAMPLE_RATE = 16000
MATCH_THRESHOLD = 0.6
NEW_THRESHOLD = 0.4
MIN_EMBED_S = 1.0

ME = "ME"
UNKNOWN = "SPEAKER ?"


@dataclass
class SpeakerLabel:
    label: str
    similarity: float | None  # best cosine similarity to a known speaker; None if not compared


def _unit(v):
    norm = np.linalg.norm(v)
    if norm == 0:
        raise ValueError("Speaker embedding is all zeros")
    return v / norm


class SpeakerTracker:
    """Online matching of embeddings against this session's speakers."""

    def __init__(self, match_threshold=MATCH_THRESHOLD, new_threshold=NEW_THRESHOLD):
        if new_threshold > match_threshold:
            raise ValueError(f"NEW_THRESHOLD {new_threshold} is above MATCH_THRESHOLD {match_threshold}")
        self.match_threshold = match_threshold
        self.new_threshold = new_threshold
        self.sums = []  # per speaker: sum of unit embeddings; its direction is the centroid

    def assign(self, embedding):
        e = _unit(np.asarray(embedding, dtype=np.float64))
        if not self.sums:
            self.sums.append(e)
            return SpeakerLabel("SPEAKER 1", None)
        sims = [float(_unit(s) @ e) for s in self.sums]
        best = int(np.argmax(sims))
        if sims[best] >= self.match_threshold:
            self.sums[best] = self.sums[best] + e
            return SpeakerLabel(f"SPEAKER {best + 1}", sims[best])
        if sims[best] < self.new_threshold:
            self.sums.append(e)
            return SpeakerLabel(f"SPEAKER {len(self.sums)}", sims[best])
        return SpeakerLabel(UNKNOWN, sims[best])


class Embedder:
    """TitaNet-Large speaker embeddings (192-dim) for 16 kHz mono float32 audio."""

    def __init__(self, device):
        from nemo.collections.asr.models import EncDecSpeakerLabelModel

        self.model = EncDecSpeakerLabelModel.from_pretrained(SPEAKER_MODEL, map_location=device).to(device).eval()

    def __call__(self, samples):
        emb, _ = self.model.infer_segment(samples)
        return emb[0].float().cpu().numpy()

    def warmup(self):
        """First call is slower (CUDA kernels, allocator); pay it before going live."""
        rng = np.random.default_rng(0)
        self((0.01 * rng.standard_normal(2 * SAMPLE_RATE)).astype(np.float32))


class SpeakerLabeler:
    def __init__(self, embed, tracker=None):
        self.embed = embed
        self.tracker = tracker or SpeakerTracker()

    def label(self, segment):
        if segment.source == "mic":
            return SpeakerLabel(ME, None)
        if segment.source != "loopback":
            raise ValueError(f"Unknown source {segment.source!r}")
        if len(segment.samples) < MIN_EMBED_S * SAMPLE_RATE:
            return SpeakerLabel(UNKNOWN, None)
        return self.tracker.assign(self.embed(segment.samples))

    @property
    def speakers(self):
        return len(self.tracker.sums)
