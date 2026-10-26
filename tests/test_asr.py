from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
import torch

from asr import SAMPLE_RATE, Recognizer

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
CLIP = Path(__file__).parent.parent / "bench" / "clips" / "hakob" / "09.wav"  # Երևանը Հայաստանի մայրաքաղաքն է։


@pytest.fixture(scope="module")
def asr():
    return Recognizer(DEVICE)


@pytest.mark.slow
def test_numpy_input_runs_and_returns_text(asr):
    out = asr.transcribe(np.zeros(SAMPLE_RATE, dtype=np.float32))
    assert isinstance(out.text_hy, str)
    assert isinstance(out.avg_logprob, float)


@pytest.mark.slow
@pytest.mark.skipif(not CLIP.exists(), reason="record the clips first: python bench/record_clips.py")
def test_recorded_clip_transcribes_to_armenian(asr):
    audio, sr = sf.read(CLIP, dtype="float32")
    assert sr == SAMPLE_RATE
    out = asr.transcribe(audio)
    assert "Հայաստան" in out.text_hy
    assert out.tokens > 0
