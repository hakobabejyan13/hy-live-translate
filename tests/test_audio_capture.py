import numpy as np
import pytest

from audio_capture import CHUNK, SAMPLE_RATE, Rechunker, ToMono16k


def stereo_sine(rate, seconds, freq, left=0.5, right=0.5):
    t = np.arange(int(rate * seconds)) / rate
    tone = np.sin(2 * np.pi * freq * t)
    return np.stack([left * tone, right * tone], axis=1).astype(np.float32)


def run_blocks(convert, audio, block):
    """Feed audio in device-sized blocks, as capture() does, and return the 16 kHz chunks."""
    rechunk = Rechunker()
    chunks = []
    for i in range(0, len(audio), block):
        chunks += rechunk(convert(audio[i:i + block]))
    return chunks


def dominant_freq(x):
    spectrum = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    return np.fft.rfftfreq(len(x), 1 / SAMPLE_RATE)[np.argmax(spectrum)]


@pytest.mark.parametrize("rate", [48000, 44100])
def test_stereo_downmixed_and_resampled_to_16k(rate):
    audio = stereo_sine(rate, 2.0, 1000)
    chunks = run_blocks(ToMono16k(rate, 2), audio, int(rate * 0.032))
    assert all(c.dtype == np.float32 and c.shape == (CHUNK,) for c in chunks)
    out = np.concatenate(chunks)
    # Streaming resampler holds back a few ms of filter delay; everything else comes out.
    assert 2.0 * SAMPLE_RATE - 2 * CHUNK <= len(out) <= 2.0 * SAMPLE_RATE
    steady = out[SAMPLE_RATE // 4:]
    assert dominant_freq(steady) == pytest.approx(1000, abs=5)
    assert np.max(np.abs(steady)) == pytest.approx(0.5, abs=0.02)


def test_downmix_is_mean_of_channels():
    audio = stereo_sine(48000, 1.0, 440, left=0.6, right=0.0)
    out = np.concatenate(run_blocks(ToMono16k(48000, 2), audio, 1536))
    assert np.max(np.abs(out[SAMPLE_RATE // 4:])) == pytest.approx(0.3, abs=0.02)


def test_block_edges_leave_no_clicks():
    """Resampling per block without carried state would put glitches at every block edge."""
    audio = stereo_sine(48000, 1.0, 300)
    out = np.concatenate(run_blocks(ToMono16k(48000, 2), audio, 1536))[SAMPLE_RATE // 4:]
    max_step = 0.5 * 2 * np.pi * 300 / SAMPLE_RATE  # largest sample-to-sample change of a clean 300 Hz sine
    assert np.max(np.abs(np.diff(out))) <= 1.05 * max_step


def test_16k_mono_passes_through_unchanged():
    audio = (0.1 * np.random.default_rng(0).standard_normal((SAMPLE_RATE, 1))).astype(np.float32)
    out = np.concatenate(run_blocks(ToMono16k(SAMPLE_RATE, 1), audio, 500))
    np.testing.assert_array_equal(out, audio[:len(out), 0])
    assert len(out) == (SAMPLE_RATE // CHUNK) * CHUNK


def test_wrong_channel_count_fails_loudly():
    with pytest.raises(ValueError, match="2\\) block"):
        ToMono16k(48000, 2)(np.zeros((100, 6), dtype=np.float32))


def test_unusable_format_fails_loudly():
    with pytest.raises(ValueError, match="Unsupported device format"):
        ToMono16k(0, 2)


def test_rechunker_keeps_remainder():
    rechunk = Rechunker()
    assert rechunk(np.ones(CHUNK - 1, dtype=np.float32)) == []
    chunks = rechunk(np.full(CHUNK + 2, 2.0, dtype=np.float32))
    assert len(chunks) == 2 and chunks[0][0] == 1.0 and chunks[0][-1] == 2.0
    assert len(rechunk.pending) == 1
