# TESTS

Run from the repo root (models download from Hugging Face on the first run):

```
pip install -r requirements.txt -r bench\requirements-bench.txt
pytest                 # everything
pytest -m "not slow"   # only the tests that load no model
```

Tests use CUDA when PyTorch sees a GPU, otherwise the CPU.

| File | Test | Checks |
|---|---|---|
| `tests/test_translate.py` | `test_max_new_tokens_grows_with_input` | Output token cap is 2 x input tokens + 16 |
| | `test_known_sentence_translates_to_english` (slow) | `Երևանը Հայաստանի մայրաքաղաքն է։` gives English with "Yerevan" and "capital", token counts set, not capped |
| | `test_empty_input_gives_empty_output` (slow) | Blank text skips the model and returns empty output with 0 tokens |
| `tests/test_asr.py` | `test_numpy_input_runs_and_returns_text` (slow) | FastConformer accepts a numpy array, as `skeleton.py` passes it |
| | `test_recorded_clip_transcribes_to_armenian` (slow) | Recorded clip `bench/clips/hakob/09.wav` contains "Հայաստան"; skipped until the clips are recorded |

Benchmarks (not unit tests, results in `bench/results/`): `bench/bench_asr.py` for ASR WER/CER and speed,
`bench/bench_mt.py` for translation BLEU/chrF, speed and token counts.
