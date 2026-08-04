#!/usr/bin/env python3
# ============================================================================
#  SkyVEx · audio_export.py  —  FMOD bank -> WAV audio exporter
#  PROVENANCE : ORIGINAL. Every line written by lingyunalingyun for SkyVEx.
#               No code taken from any other repository.
#  AUTHOR     : lingyunalingyun · https://github.com/lingyunalingyun
#  LICENSE    : MIT (see LICENSE)
#  NOTE       : This module only orchestrates the bundled vgmstream-cli.exe
#               (see _vgmstream/, its own license in _vgmstream/COPYING). It
#               does not contain any vgmstream code.
# ============================================================================
"""
Export Sky: Children of the Light streamed audio (FMOD `.streams.bank`) to WAV.

Sky ships music/SFX as FMOD Studio banks under `Data/Audio/Fmod/`. The streamed
audio (`*.streams.bank`) is Custom Vorbis / FMOD FADPCM and is decoded here by
shelling out to the bundled vgmstream-cli. Each bank holds several "subsongs";
they are written as `<index>_<stream name>.wav`. The `*.assets.bank` sample
banks are encrypted and are skipped.
"""

import os
import re
import sys
import subprocess

if getattr(sys, "frozen", False):
    SCRIPT_DIR = sys._MEIPASS          # PyInstaller bundle root
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

VGM_EXE = os.path.join(SCRIPT_DIR, "_vgmstream", "vgmstream-cli.exe")

# Hide the console window when launched from a windowed (pythonw / frozen) app.
_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def is_available():
    """True if the bundled vgmstream-cli is present."""
    return os.path.isfile(VGM_EXE)


def find_streams_banks(root):
    """Return all `*.streams.bank` files under root (recursive), sorted."""
    banks = []
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if f.lower().endswith(".streams.bank"):
                banks.append(os.path.join(dirpath, f))
    return sorted(banks)


def _count_wavs(d):
    try:
        return sum(1 for f in os.listdir(d) if f.lower().endswith(".wav"))
    except OSError:
        return 0


def _run(args):
    return subprocess.run(
        [VGM_EXE, *args], capture_output=True, text=True,
        creationflags=_NO_WINDOW,
    )


def subsong_count(bank):
    """Number of subsongs in a bank (0 if it can't be opened, e.g. encrypted)."""
    if not is_available():
        return 0
    out = _run(["-m", bank]).stdout or ""
    if "couldn't" in out or "failed" in out or "metadata" not in out:
        return 0
    m = re.search(r"stream count:\s*(\d+)", out)
    return int(m.group(1)) if m else 1


def subsong_name(bank, index):
    """Internal stream name of subsong `index` (1-based); '' if unknown."""
    if not is_available():
        return ""
    out = _run(["-s", str(index), "-m", bank]).stdout or ""
    m = re.search(r"stream name:\s*(.+)", out)
    return m.group(1).strip() if m else ""


def decode_subsong(bank, index, out_wav):
    """Decode a single subsong to `out_wav`. Returns True on success."""
    if not is_available():
        return False
    try:
        _run(["-s", str(index), "-o", out_wav, bank])
    except Exception:
        return False
    return os.path.isfile(out_wav) and os.path.getsize(out_wav) > 0


def export_audio(root, out_dir, log=print, progress=None):
    """Decode every streamed FMOD bank under `root` to WAV.

    Files land in `<out_dir>/Audio/<bank name>/<index>_<stream name>.wav`.
    Returns the total number of WAV files written.
    `progress(done, total)` is called after each bank if given.
    """
    if not is_available():
        log(f"[ERR] 找不到 vgmstream-cli: {VGM_EXE}\n")
        return 0

    banks = find_streams_banks(root)
    if not banks:
        log(f"[WARN] 未在 {root} 下找到 .streams.bank 音频文件\n")
        return 0

    audio_root = os.path.join(out_dir, "Audio")
    os.makedirs(audio_root, exist_ok=True)
    log(f"发现 {len(banks)} 个音频 bank，开始解码...\n\n")

    total = 0
    for i, bank in enumerate(banks):
        name = os.path.basename(bank)[:-len(".streams.bank")]
        dest = os.path.join(audio_root, name)
        os.makedirs(dest, exist_ok=True)
        out_pattern = os.path.join(dest, "?03s_?n.wav")
        before = _count_wavs(dest)

        try:
            # -s 1 -S 0 : all subsongs; wildcards ?03s = padded index, ?n = name
            subprocess.run(
                [VGM_EXE, "-s", "1", "-S", "0", "-o", out_pattern, bank],
                capture_output=True, text=True, creationflags=_NO_WINDOW,
            )
        except Exception as e:  # noqa: BLE001 - report and keep going
            log(f"[ERR] {name}: {e}\n")
            if progress:
                progress(i + 1, len(banks))
            continue

        made = _count_wavs(dest) - before
        total += made
        log(f"[OK] {name}: {made} 段音频\n")
        if progress:
            progress(i + 1, len(banks))

    log(f"\n[完成] 共导出 {total} 个 WAV → {audio_root}\n")
    return total
