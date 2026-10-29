"""Armenian speech recognition with NVIDIA FastConformer (NeMo), RNNT greedy decoding.

Chosen by bench/bench_asr.py: FLEURS hy_am WER 10.6%, about 0.08 s per clip on an RTX 5070 Laptop GPU.
"""

from dataclasses import dataclass

import numpy as np
import nemo.collections.asr as nemo_asr

ASR_MODEL = "nvidia/stt_hy_fastconformer_hybrid_large_pc"
SAMPLE_RATE = 16000


@dataclass
class Transcript:
    text_hy: str
    avg_logprob: float  # transducer log-prob per token; closer to 0 is more confident
    tokens: int


class Recognizer:
    def __init__(self, device):
        self.model = nemo_asr.models.ASRModel.from_pretrained(ASR_MODEL, map_location=device).to(device).eval()
        # The RNNT joint skips log_softmax on CUDA by default (the training loss does it), so hypothesis scores
        # would be raw logits on GPU but log-probs on CPU. Force it so avg_logprob means the same on both.
        # argmax is unchanged, so transcripts are identical.
        self.model.joint.log_softmax = True

    def transcribe(self, samples):
        """samples: 16 kHz mono float32 numpy array."""
        out = self.model.transcribe([samples], batch_size=1, return_hypotheses=True, verbose=False)
        if isinstance(out, tuple):  # some NeMo versions return (best, all) for transducers
            out = out[0]
        hyp = out[0]
        tokens = len(hyp.y_sequence)
        return Transcript(hyp.text.strip(), float(hyp.score) / max(tokens, 1), tokens)

    def warmup(self):
        """First transcribe() call is several times slower (CUDA kernels, allocator); pay it before going live."""
        rng = np.random.default_rng(0)
        self.transcribe((0.01 * rng.standard_normal(2 * SAMPLE_RATE)).astype(np.float32))
