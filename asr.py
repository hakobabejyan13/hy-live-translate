"""Armenian speech recognition with NVIDIA FastConformer (NeMo), RNNT greedy decoding.

Chosen by bench/bench_asr.py: FLEURS hy_am WER 10.6%, about 0.08 s per clip on an RTX 5070 Laptop GPU.

Optional phrase boosting (NeMo GPU-PB boosting tree): the glossary's Armenian spellings of loanwords are boosted
during greedy decoding, so the model writes "միթինգ" as one word instead of "մի թինգ" and glossary.py can match
it. bench/bench_boost.py measured it on 11 recorded loanword clips (2026-10-30): loanwords reaching MT 11 -> 18
at alpha 2.0, plain-Armenian control WER unchanged (0.0%), ASR 0.05 -> 0.11 s per clip.
"""

import copy

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


DEFAULT_BOOST_ALPHA = 2.0


class Recognizer:
    def __init__(self, device):
        self.model = nemo_asr.models.ASRModel.from_pretrained(ASR_MODEL, map_location=device).to(device).eval()
        # The RNNT joint skips log_softmax on CUDA by default (the training loss does it), so hypothesis scores
        # would be raw logits on GPU but log-probs on CPU. Force it so avg_logprob means the same on both.
        # argmax is unchanged, so transcripts are identical.
        self.model.joint.log_softmax = True

    def set_boosting(self, phrases, alpha):
        """Greedy-batch RNNT decoding, boosting `phrases` (Armenian words) with weight `alpha`; alpha 0 = off."""
        from omegaconf import OmegaConf, open_dict
        from nemo.collections.asr.parts.context_biasing.boosting_graph_batched import BoostingTreeModelConfig

        if alpha > 0 and not phrases:
            raise ValueError("Boosting needs at least one phrase")
        tree = BoostingTreeModelConfig(key_phrases_list=list(phrases), use_triton=False) if alpha > 0 \
            else BoostingTreeModelConfig()  # use_triton=False: Triton is usually missing on Windows
        cfg = copy.deepcopy(self.model.cfg.decoding)
        with open_dict(cfg):
            cfg.strategy = "greedy_batch"
            cfg.greedy.boosting_tree = OmegaConf.structured(tree)
            cfg.greedy.boosting_tree_alpha = float(alpha)
        self.model.change_decoding_strategy(cfg, decoder_type="rnnt", verbose=False)

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
