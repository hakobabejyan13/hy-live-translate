"""Armenian -> English translation with NLLB-200 distilled 600M.

fp16 on CUDA, fp32 on CPU. Greedy decoding, with the output capped at 2x the input tokens + 16 so a
repetition loop cannot run on and blow the latency budget; a capped line is reported, never hidden.
"""

from dataclasses import dataclass

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

MT_MODEL = "facebook/nllb-200-distilled-600M"
SRC_LANG = "hye_Armn"
TGT_LANG = "eng_Latn"
WARMUP_TEXT = "Բարև ձեզ, ինչպե՞ս եք։"


@dataclass
class Translation:
    text_en: str
    tokens_in: int  # source tokens, including the language and end tokens
    tokens_out: int  # generated tokens, including the language and end tokens
    capped: bool  # True when generation stopped at the token cap instead of at an end token


def max_new_tokens(tokens_in):
    return 2 * tokens_in + 16


class Translator:
    def __init__(self, device):
        self.device = device
        self.dtype = torch.float16 if device == "cuda" else torch.float32
        self.tokenizer = AutoTokenizer.from_pretrained(MT_MODEL, src_lang=SRC_LANG)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(MT_MODEL, torch_dtype=self.dtype).to(device).eval()
        self.tgt_id = self.tokenizer.convert_tokens_to_ids(TGT_LANG)

    def translate(self, text_hy):
        if not text_hy.strip():
            return Translation("", 0, 0, False)
        inputs = self.tokenizer(text_hy, return_tensors="pt").to(self.device)
        tokens_in = inputs["input_ids"].shape[1]
        cap = max_new_tokens(tokens_in)
        with torch.inference_mode():
            out = self.model.generate(**inputs, forced_bos_token_id=self.tgt_id, num_beams=1, do_sample=False,
                                      max_new_tokens=cap)
        tokens_out = out.shape[1] - 1  # the first position is the decoder start token, not generated
        text_en = self.tokenizer.decode(out[0], skip_special_tokens=True)
        return Translation(text_en, tokens_in, tokens_out, tokens_out >= cap)

    def warmup(self):
        """First generate() call is several times slower (CUDA kernels, allocator); pay it before going live."""
        self.translate(WARMUP_TEXT)
