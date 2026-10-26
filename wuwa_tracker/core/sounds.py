"""Original sound effects for the Convene animation, synthesised with numpy (no game audio is used).

The WAV files are generated once into the app's data folder (…/WuwaTracker/sounds) and re-created when
SOUND_VERSION changes.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 44100
SOUND_VERSION = 2


def _t(sec):
    return np.linspace(0, sec, int(SR * sec), endpoint=False)


def _env(n, attack=0.01, release=0.3, sec=None):
    sec = sec or n / SR
    t = np.linspace(0, sec, n, endpoint=False)
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    r = np.clip((sec - t) / max(release, 1e-4), 0, 1)
    return a * r


def _bell(freq, sec, decay=3.0, bright=0.35):
    t = _t(sec)
    partials = [(1, 1.0), (2.01, bright), (3.02, bright * 0.45), (4.2, bright * 0.2)]
    s = sum(a * np.sin(2 * np.pi * freq * m * t) for m, a in partials)
    return s * np.exp(-decay * t) * _env(len(t), 0.004, 0.05)


def _noise(sec, seed=1):
    return np.random.default_rng(seed).uniform(-1, 1, int(SR * sec))


def _lowpass(x, alpha):
    """One-pole low-pass; alpha can be an array (time-varying cutoff)."""
    y = np.empty_like(x)
    acc = 0.0
    a = np.broadcast_to(alpha, x.shape)
    for i in range(len(x)):
        acc += a[i] * (x[i] - acc)
        y[i] = acc
    return y


def _mix(*parts):
    n = max(len(p) for p, _ in parts)
    out = np.zeros(n)
    for p, start in parts:
        s = int(start * SR)
        out[s:s + len(p)] += p[: max(0, n - s)]
    return out


def _norm(x, peak=0.8):
    m = np.max(np.abs(x)) or 1.0
    return x / m * peak


def whoosh():
    sec = 1.9
    t = _t(sec)
    n = _noise(sec, 3)
    cutoff = 0.02 + 0.25 * (t / sec) ** 2            # opens up as the comet rises
    w = _lowpass(n, cutoff)
    tone = 0.25 * np.sin(2 * np.pi * (180 + 520 * (t / sec) ** 2) * t)
    return _norm((w * 2.2 + tone) * _env(len(t), 0.35, 0.25), 0.55)


def shimmer():                                        # comet turning gold
    notes = [1046.5, 1318.5, 1568.0, 2093.0, 2637.0]
    return _norm(_mix(*[(_bell(f, 1.2, 4.5, 0.5) * 0.6, i * 0.06) for i, f in enumerate(notes)]), 0.5)


def burst(rarity):
    sec = 1.6 if rarity == 5 else 1.1
    t = _t(sec)
    thump = np.sin(2 * np.pi * (90 - 40 * t / sec) * t) * np.exp(-5 * t)
    hiss = _lowpass(_noise(sec, 7), 0.25) * np.exp(-6 * t) * 0.6
    chord = {3: [523.3, 659.3], 4: [587.3, 740.0, 880.0], 5: [523.3, 659.3, 784.0, 1046.5]}[rarity]
    bells = _mix(*[(_bell(f, sec, 2.2 if rarity == 5 else 3.0) * 0.5, 0.02 * i) for i, f in enumerate(chord)])
    return _norm(_mix((thump * 1.2, 0), (hiss, 0), (bells, 0.03)), 0.85 if rarity == 5 else 0.7)


def reveal(rarity):
    if rarity == 3:
        return _norm(_bell(784.0, 0.5, 7, 0.2), 0.35)
    if rarity == 4:
        return _norm(_mix((_bell(880.0, 0.9, 4), 0), (_bell(1318.5, 0.9, 4), 0.09)), 0.5)
    arp = [523.3, 659.3, 784.0, 1046.5, 1318.5]
    return _norm(_mix(*[(_bell(f, 1.8, 2.2, 0.45), i * 0.08) for i, f in enumerate(arp)],
                      (_bell(261.6, 1.8, 1.6, 0.2) * 0.7, 0)), 0.7)


def star(i):                                          # one tick per star, rising pitch
    return _norm(_bell(1200 * (2 ** (i / 6)), 0.25, 14, 0.4), 0.3)


def write_wav(path: Path, x: np.ndarray):
    data = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(data.tobytes())


SOUNDS = {
    "whoosh": whoosh,
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
        stamp.write_text("ok")
    return out
