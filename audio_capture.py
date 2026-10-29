"""Audio capture: microphone and WASAPI loopback (system audio) as 16 kHz mono float32 chunks.

Both sources go through the same path. The device is opened at its native format (read from the
Windows audio engine, usually 48 kHz stereo), then every block is downmixed to mono (mean of the
channels) and resampled to 16 kHz with a streaming soxr resampler, which keeps filter state across
blocks so there are no clicks at block edges. Output is cut into 512-sample chunks, the size Silero
VAD needs.

Library: `soundcard` (WASAPI, including loopback). It does not expose the device sample rate, so
`native_format` reads it the same way soundcard reads the channel count (PKEY_AudioEngine_DeviceFormat),
using soundcard internals; requirements.txt pins the soundcard version for that reason.
"""

import sys
import threading
import time
from dataclasses import dataclass

import numpy as np
import soxr

SAMPLE_RATE = 16000
CHUNK = 512  # Silero VAD expects 512-sample chunks at 16 kHz
BLOCK_S = 0.032  # how much audio to read from the device per call
BUFFER_S = 0.2  # WASAPI buffer size; headroom so a slow read never drops audio


@dataclass
class AudioChunk:
    source: str  # "mic" or "loopback"
    samples: np.ndarray  # 16 kHz mono float32, CHUNK samples
    t_captured: float  # wall time the device block holding the end of this chunk was read


class ToMono16k:
    """Downmix (frames x channels) blocks at in_rate to mono and resample them to 16 kHz, keeping state."""

    def __init__(self, in_rate, channels):
        if in_rate <= 0 or channels <= 0:
            raise ValueError(f"Unsupported device format: {in_rate} Hz, {channels} channels")
        self.in_rate = in_rate
        self.channels = channels
        self.resampler = None if in_rate == SAMPLE_RATE else soxr.ResampleStream(in_rate, SAMPLE_RATE, 1,
                                                                                 dtype="float32")

    def __call__(self, block):
        if block.ndim != 2 or block.shape[1] != self.channels:
            raise ValueError(f"Expected a (frames, {self.channels}) block, got shape {block.shape}")
        mono = block.astype(np.float32).mean(axis=1)
        return mono if self.resampler is None else self.resampler.resample_chunk(mono)


class Rechunker:
    """Collect variable-length 16 kHz audio and hand it out in fixed CHUNK-sample pieces."""

    def __init__(self):
        self.pending = np.zeros(0, dtype=np.float32)

    def __call__(self, samples):
        self.pending = np.concatenate([self.pending, samples])
        n = len(self.pending) // CHUNK
        chunks = [self.pending[i * CHUNK:(i + 1) * CHUNK] for i in range(n)]
        self.pending = self.pending[n * CHUNK:]
        return chunks


def _soundcard():
    if sys.platform != "win32":
        raise SystemExit("Audio capture needs Windows (WASAPI loopback).")
    import soundcard
    return soundcard


def native_format(device):
    """(sample rate, channels) of a soundcard device as the Windows audio engine runs it (shared mode)."""
    from soundcard import mediafoundation as mf

    store = mf._ffi.new("IPropertyStore **")
    ptr = device._device_ptr()
    hr = ptr[0][0].lpVtbl.OpenPropertyStore(ptr[0], 0, store)
    mf._com.release(ptr)
    mf._com.check_error(hr)
    prop = mf._PropVariant()
    key = mf._ffi.new("PROPERTYKEY *", [[0xf19f064d, 0x82c, 0x4e27, [0xbc, 0x73, 0x68, 0x82, 0xa1, 0xbb, 0x8e, 0x4c]],
                                        0])  # PKEY_AudioEngine_DeviceFormat
    hr = store[0][0].lpVtbl.GetValue(store[0], key, prop.ptr)
    mf._com.release(store)
    mf._com.check_error(hr)
    if prop.ptr[0].vt != 65:
        raise RuntimeError(f"{device.name}: device format property is not a blob")
    blob = mf._ffi.cast("BLOB_PROPVARIANT *", prop.ptr)
    fmt = mf._ffi.cast("WAVEFORMATEX *", blob[0].blob.pBlobData)
    return int(fmt[0].nSamplesPerSec), int(fmt[0].nChannels)


def open_device(source, name=None):
    """Find the mic (default or by name) or the speaker to loop back (default or by name)."""
    sc = _soundcard()
    if source == "mic":
        return sc.default_microphone() if name is None else sc.get_microphone(name)
    speaker = sc.default_speaker() if name is None else sc.get_speaker(name)
    return sc.get_microphone(speaker.id, include_loopback=True)  # soundcard's loopback "microphone" for that speaker


def list_devices():
    sc = _soundcard()
    print("Microphones (--mic NAME):")
    for m in sc.all_microphones():
        rate, ch = native_format(m)
        print(f"  {m.name}  [{rate} Hz, {ch} ch]")
    print("Speakers to capture as loopback (--speaker NAME):")
    for s in sc.all_speakers():
        rate, ch = native_format(s)
        print(f"  {s.name}  [{rate} Hz, {ch} ch]")
    print(f"Defaults: mic = {sc.default_microphone().name}, speaker = {sc.default_speaker().name}")


def capture(source, device, out, stop):
    """Read `device` until `stop` is set and put AudioChunk(source, 16 kHz mono) objects on `out`."""
    # This runs in its own thread. soundcard initialises COM only in the thread that imported it, so make
    # sure this thread is in the multithreaded apartment too (S_FALSE = already initialised is fine).
    import ctypes
    hr = ctypes.windll.ole32.CoInitializeEx(None, 0)  # COINIT_MULTITHREADED
    if hr < 0:
        raise RuntimeError(f"CoInitializeEx failed in the {source} capture thread: {hr & 0xFFFFFFFF:#010x}")

    rate, channels = native_format(device)
    convert = ToMono16k(rate, channels)
    rechunk = Rechunker()
    print(f"{source}: {device.name} at {rate} Hz, {channels} ch -> {SAMPLE_RATE} Hz mono")
    with device.recorder(samplerate=rate, channels=channels, blocksize=int(rate * BUFFER_S)) as rec:
        frames = int(rate * BLOCK_S)
        while not stop.is_set():
            block = rec.record(numframes=frames)
            t = time.time()
            for chunk in rechunk(convert(block)):
                out.put(AudioChunk(source, chunk, t))


def start(source, device, out, stop):
    """Start capture() in a daemon thread and return the thread."""
    thread = threading.Thread(target=capture, args=(source, device, out, stop), name=f"capture-{source}", daemon=True)
    thread.start()
    return thread
