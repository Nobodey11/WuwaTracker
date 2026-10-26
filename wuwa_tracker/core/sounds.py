"""Original sound effects for the Convene animation, synthesised with numpy.

Style: cinematic and "tidal" in the spirit of the game's Convene, but no game audio is used or copied.
  * deep sub-bass swells and drops, airy wind risers
  * glassy, slightly inharmonic crystal chimes (instead of plain bells)
  * soft choir-like pads (detuned stacked partials with slow vibrato)
  * everything in stereo through a long hall reverb (FFT convolution with a synthetic impulse)

WAVs are generated once into the app data folder and re-created when SOUND_VERSION changes.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 44100
SOUND_VERSION = 3
RNG = np.random.default_rng(11)


# ---------------------------------------------------------------- building blocks
def _t(sec):
    return np.arange(int(SR * sec)) / SR


def _env(n, attack, release):
    t = np.arange(n) / SR
    sec = n / SR
    return np.clip(t / max(attack, 1e-4), 0, 1) * np.clip((sec - t) / max(release, 1e-4), 0, 1)


def _lowpass(x, alpha):
    """One-pole low-pass, alpha may vary over time (array)."""
    a = np.broadcast_to(np.asarray(alpha, dtype=float), x.shape)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += a[i] * (x[i] - acc)
        y[i] = acc
    return y


def _crystal(freq, sec, decay=2.5, amp=1.0):
    """Glassy chime: slightly inharmonic partials + a short bright 'tick' transient."""
    t = _t(sec)
    partials = [(1.0, 1.0), (2.76, 0.45), (5.40, 0.22), (8.93, 0.10)]
    s = sum(a * np.sin(2 * np.pi * freq * m * t + RNG.uniform(0, 6)) * np.exp(-decay * (1 + m * 0.35) * t)
            for m, a in partials)
    click = RNG.uniform(-1, 1, len(t)) * np.exp(-t * 900) * 0.15
    return amp * (s + click) * _env(len(t), 0.002, 0.05)


def _pad(freqs, sec, attack=0.5, release=0.8, bright=0.5):
    """Choir-like pad: detuned stacked partials with slow vibrato."""
    t = _t(sec)
    out = np.zeros(len(t))
    for f in freqs:
        for det in (-0.004, 0.0, 0.0045):
            vib = 1 + 0.003 * np.sin(2 * np.pi * 5.2 * t + RNG.uniform(0, 6))
            ph = 2 * np.pi * f * (1 + det) * np.cumsum(vib) / SR
            out += np.sin(ph) + bright * 0.35 * np.sin(2 * ph) + bright * 0.15 * np.sin(3 * ph)
    return out / (len(freqs) * 3) * _env(len(t), attack, release)


def _sub(f0, f1, sec, decay=2.0):
    t = _t(sec)
    f = f0 + (f1 - f0) * (t / sec)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-decay * t)


def _noise(sec):
    return RNG.uniform(-1, 1, int(SR * sec))


def _place(n, *parts):
    """Mix (signal, start_seconds) parts into a buffer of n samples."""
    out = np.zeros(n)
    for sig, start in parts:
        s = int(start * SR)
        if s >= n:
            continue
        m = min(len(sig), n - s)
        out[s:s + m] += sig[:m]
    return out


def _stereo(mono, width=0.25, delay_ms=11):
    """Widen a mono signal: small inter-channel delay + opposite filtering."""
    d = int(SR * delay_ms / 1000)
    left = mono
    right = np.concatenate([np.zeros(d), mono[:-d]]) if d else mono
    side = (left - right) * width
    return np.stack([mono + side, mono - side], axis=1)


_IR_CACHE: dict = {}


def _impulse(sec=2.6, damp=3.2):
    key = (sec, damp)
    if key not in _IR_CACHE:
        t = _t(sec)
        ir = np.stack([RNG.normal(0, 1, len(t)), RNG.normal(0, 1, len(t))], axis=1)
        ir *= np.exp(-damp * t)[:, None]
        ir[:, 0] = _lowpass(ir[:, 0], 0.35)           # darker tail
        ir[:, 1] = _lowpass(ir[:, 1], 0.35)
        ir /= np.sqrt((ir ** 2).sum(axis=0))
        _IR_CACHE[key] = ir
    return _IR_CACHE[key]


def _reverb(st, wet=0.35, sec=2.6):
    """Hall reverb via FFT convolution. st: (n, 2) stereo. Output is longer (tail)."""
    ir = _impulse(sec)
    n = len(st) + len(ir) - 1
    size = 1 << (n - 1).bit_length()
    out = np.zeros((n, 2))
    for c in range(2):
        out[:, c] = np.fft.irfft(np.fft.rfft(st[:, c], size) * np.fft.rfft(ir[:, c], size), size)[:n]
    dry = np.zeros((n, 2)); dry[:len(st)] = st
    return dry * (1 - wet) + out * wet * 3.0


def _finish(st, peak=0.85, fade=0.25):
    m = np.max(np.abs(st)) or 1.0
    st = st / m * peak
    k = int(SR * fade)
    st[-k:] *= np.linspace(1, 0, k)[:, None]
    return st


# ---------------------------------------------------------------- the sounds
def launch():
    """Tide rising: deep swell + airy wind riser + faint shimmering pad."""
    sec = 2.1
    n = int(SR * sec)
    t = _t(sec)
    wind = _lowpass(_noise(sec), 0.01 + 0.18 * (t / sec) ** 2) * 3.0 * _env(n, 0.6, 0.2)
    swell = _sub(38, 70, sec, 0.0) * (t / sec) ** 1.5 * 0.9
    pad = _pad([220.0, 329.6, 440.0], sec, 1.4, 0.3, 0.3) * 0.5
    riser = np.sin(2 * np.pi * np.cumsum(300 + 900 * (t / sec) ** 3) / SR) * (t / sec) ** 4 * 0.25
    mono = wind + swell + pad + riser
    return _finish(_reverb(_stereo(mono, 0.35), 0.3, 2.0), 0.6)


def shimmer():
    """The comet turning gold: rapid ascending crystal cascade over a bright pad."""
    sec = 1.6
    n = int(SR * sec)
    notes = [880.0, 1108.7, 1318.5, 1760.0, 2217.5, 2637.0, 3520.0]
    casc = _place(n, *[(_crystal(f, 1.2, 3.0, 0.7), i * 0.045) for i, f in enumerate(notes)])
    pad = _pad([659.3, 830.6, 987.8], sec, 0.15, 0.6, 0.6) * 0.5
    return _finish(_reverb(_stereo(casc + pad, 0.4), 0.45), 0.55)


def burst(rarity):
    """Impact: sub drop + air crack + crystal chord (+ choir and sparkles for 5★)."""
    sec = {3: 1.4, 4: 1.8, 5: 2.6}[rarity]
    n = int(SR * sec)
    t = _t(sec)
    drop = _sub(110, 32, 0.9, 4.5) * (1.3 if rarity == 5 else 1.0)
    crack = _lowpass(_noise(0.6), 0.5) * np.exp(-_t(0.6) * 9) * 0.9
    chord = {3: [392.0, 587.3, 784.0],
             4: [440.0, 554.4, 659.3, 880.0],
             5: [523.3, 659.3, 784.0, 1046.5, 1318.5]}[rarity]
    bells = _place(n, *[(_crystal(f, sec, 1.6, 0.55), 0.015 * i) for i, f in enumerate(chord)])
    parts = [(drop, 0), (crack, 0), (bells, 0.02)]
    if rarity >= 4:
        parts.append((_pad([f / 2 for f in chord[:3]], sec * 0.9, 0.05, 1.0, 0.6) * (0.9 if rarity == 5 else 0.5), 0.0))
    if rarity == 5:
        spark = [(_crystal(RNG.uniform(2000, 4200), 0.6, 6, 0.25), 0.25 + i * 0.07) for i in range(12)]
        parts += spark
    mono = _place(n, *parts) * _env(n, 0.001, 0.3)
    return _finish(_reverb(_stereo(mono, 0.3), 0.4 if rarity == 5 else 0.32, 2.8), 0.9 if rarity == 5 else 0.75)


def reveal(rarity):
    if rarity == 3:          # quick glassy 'ting'
        sec = 0.8
        n = int(SR * sec)
        mono = _place(n, (_crystal(1174.7, sec, 4.5, 0.8), 0), (_crystal(1760.0, sec, 6, 0.3), 0.03))
        return _finish(_reverb(_stereo(mono, 0.2), 0.3, 1.4), 0.4)
    if rarity == 4:          # two-tone shimmer with a soft whoosh
        sec = 1.4
        n = int(SR * sec)
        whoosh = _lowpass(_noise(0.5), 0.12) * _env(int(SR * 0.5), 0.25, 0.2) * 1.5
        mono = _place(n, (whoosh, 0), (_crystal(987.8, sec, 2.8, 0.8), 0.2), (_crystal(1480.0, sec, 2.8, 0.7), 0.3),
                      (_pad([493.9, 740.0], 1.1, 0.1, 0.7, 0.5) * 0.4, 0.2))
        return _finish(_reverb(_stereo(mono, 0.3), 0.35), 0.6)
    # 5★: rising whoosh into a big choir chord + ascending crystal arpeggio + sub hit
    sec = 3.0
    n = int(SR * sec)
    t5 = _t(0.6)
    rise = _lowpass(_noise(0.6), 0.02 + 0.3 * (t5 / 0.6) ** 2) * _env(len(t5), 0.4, 0.05) * 2.5
    arp = [(_crystal(f, 2.2, 1.8, 0.7), 0.6 + i * 0.09) for i, f in enumerate([523.3, 659.3, 784.0, 1046.5, 1318.5, 1568.0])]
    choir = _pad([261.6, 329.6, 392.0, 523.3], 2.4, 0.08, 1.2, 0.7) * 1.1
    hit = _sub(80, 40, 1.2, 3.0) * 0.9
    mono = _place(n, (rise, 0), (hit, 0.6), (choir, 0.6), *arp)
    return _finish(_reverb(_stereo(mono, 0.35), 0.42, 2.8), 0.85)


def star(i):
    """Star pop: small crystal ping, rising a whole tone each star."""
    sec = 0.6
    n = int(SR * sec)
    f = 1567.98 * (2 ** (2 * i / 12))
    mono = _place(n, (_crystal(f, sec, 7, 0.8), 0))
    return _finish(_reverb(_stereo(mono, 0.25), 0.3, 1.2), 0.32)


# ---------------------------------------------------------------- files
def write_wav(path: Path, st: np.ndarray):
    if st.ndim == 1:
        st = np.stack([st, st], axis=1)
    data = (np.clip(st, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(data.tobytes())


SOUNDS = {
    "whoosh": launch,
    "shimmer": shimmer,
    **{f"burst{r}": (lambda r=r: burst(r)) for r in (3, 4, 5)},
    **{f"reveal{r}": (lambda r=r: reveal(r)) for r in (3, 4, 5)},
    **{f"star{i}": (lambda i=i: star(i)) for i in range(5)},
}


def ensure_sounds(folder: Path) -> dict[str, Path]:
    """Generate the WAVs if missing/outdated. Returns name -> path."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = folder / f"v{SOUND_VERSION}"
    out = {name: folder / f"{name}.wav" for name in SOUNDS}
    if not stamp.exists() or not all(p.exists() for p in out.values()):
        for name, fn in SOUNDS.items():
            write_wav(out[name], fn())
        for old in folder.glob("v*"):
            old.unlink()
        stamp.write_text("ok")
    return out
