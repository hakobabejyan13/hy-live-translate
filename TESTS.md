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
| | `test_recorded_clip_transcribes_to_armenian` (slow) | Recorded clip `bench/clips/hakob/09.wav` contains "Հայաստան" and `avg_logprob` is a log-prob (between -5 and 0) on CPU and GPU; skipped until the clips are recorded |

| `tests/test_audio_capture.py` | `test_stereo_downmixed_and_resampled_to_16k` (48 kHz and 44.1 kHz) | Stereo 1 kHz tone fed in 32 ms device blocks comes out as 512-sample float32 chunks at 16 kHz: right length (minus the resampler's few ms of delay), 1 kHz peak, amplitude kept |
| | `test_downmix_is_mean_of_channels` | Tone on the left channel only comes out at half amplitude |
| | `test_block_edges_leave_no_clicks` | No sample-to-sample jump larger than a clean sine allows, so resampler state carries across blocks |
| | `test_16k_mono_passes_through_unchanged` | A 16 kHz mono device is not resampled |
| | `test_wrong_channel_count_fails_loudly`, `test_unusable_format_fails_loudly` | Unexpected device formats raise instead of producing wrong-speed audio |
| | `test_rechunker_keeps_remainder` | Leftover samples are carried to the next chunk, none lost |
| `tests/test_vad.py` (scripted detector in place of Silero) | `test_segment_cut_at_pause_has_exact_samples_and_times` | Segment holds exactly the start..end samples; `t_speech_end` and `t_closing_chunk` are right |
| | `test_long_speech_is_cut_at_max_length_and_continues` | Speech longer than 5 s is cut within the last 2 s before the 5 s mark, flagged `forced_cut`, and no audio is lost or doubled across cuts |
| | `test_forced_cut_lands_in_the_quiet_gap_not_mid_word` | A forced cut goes into the quietest 50 ms (a pause between words), and the next segment starts right after it |
| | `test_end_right_after_forced_cut_emits_nothing_more` | No empty segment after a forced cut |
| | `test_buffer_does_not_grow_in_silence` | Only ~1 s of pre-roll is kept while nobody speaks |
| | `test_chunk_from_other_source_fails_loudly` | A mic chunk can never reach the loopback VAD or the reverse |
| `tests/test_speaker.py` (fake embeddings) | `test_mic_is_always_me_without_embedding` | Mic segments are `ME`, no embedding computed |
| | `test_short_loopback_segment_is_unknown_without_embedding` | Loopback segments under 1 s are `SPEAKER ?` |
| | `test_first_remote_voice_is_speaker_1` | First remote voice is `SPEAKER 1` |
| | `test_match_new_and_uncertain` | Similarity >= match threshold -> same speaker; < new threshold -> next number; in between -> `SPEAKER ?` |
| | `test_thresholds_are_inclusive_for_match_only` | Exactly at the match threshold matches; exactly at the new threshold is uncertain |
| | `test_numbering_follows_first_appearance_and_matches_best_speaker` | Speakers numbered in order of first appearance; a segment goes to the closest speaker |
| | `test_uncertain_segment_does_not_move_centroid` | `SPEAKER ?` segments do not change what a speaker sounds like |
| | `test_centroid_is_scale_invariant` | Embedding length does not matter, only direction |
| | `test_zero_embedding_and_bad_thresholds_fail_loudly` | All-zero embedding or new threshold above match threshold raise |
| | `test_titanet_embedding_shape_and_self_similarity` (slow) | Real TitaNet gives a 192-dim embedding; the same clip twice has similarity > 0.99 |

Not covered by unit tests (needs Windows audio devices): opening the WASAPI mic and loopback in
`audio_capture.capture()`. Check it live with `python skeleton.py --list-devices`, then a call.

Benchmarks (not unit tests, results in `bench/results/`): `bench/bench_asr.py` for ASR WER/CER and speed,
`bench/bench_mt.py` for translation BLEU/chrF, speed and token counts.
