"""Pre-deployment script: generate Thai WAV files for SeismoGuard-R audio alerts.

Run ONCE on a machine with internet access before copying seismoguard/ to the robot:

    pip install gtts pydub
    apt install ffmpeg   # or brew install ffmpeg on macOS
    python scripts/generate_audio.py

Output: seismoguard/response/audio/class{1,2,3}_{warning,evacuate,critical}.wav
"""

import os
import subprocess
import sys
import tempfile

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_AUDIO_DIR  = os.path.join(_SCRIPT_DIR, "..", "seismoguard", "response", "audio")

_ALERTS = {
    1: (
        "class1_warning.wav",
        "ระวัง เกิดแผ่นดินไหวระดับปานกลาง กรุณาอยู่ในที่ปลอดภัย",
    ),
    2: (
        "class2_evacuate.wav",
        "อพยพทันที เกิดแผ่นดินไหวรุนแรง กรุณาออกจากอาคาร",
    ),
    3: (
        "class3_critical.wav",
        "อันตรายวิกฤต เกิดแผ่นดินไหวรุนแรงมาก กรุณาออกจากพื้นที่ทันที",
    ),
}


def _ffmpeg_mp3_to_wav(mp3_path: str, wav_path: str) -> None:
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", mp3_path, wav_path],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()}")


def main() -> None:
    try:
        from gtts import gTTS
    except ImportError:
        print("ERROR: gtts not installed. Run: pip install gtts", file=sys.stderr)
        sys.exit(1)

    os.makedirs(_AUDIO_DIR, exist_ok=True)

    for cls, (filename, text) in _ALERTS.items():
        out_path = os.path.join(_AUDIO_DIR, filename)
        if os.path.exists(out_path):
            print(f"  [skip] {filename} already exists")
            continue

        print(f"  [gen]  class {cls}: {filename}")
        tts = gTTS(text=text, lang="th", slow=False)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            tts.save(tmp_path)
            _ffmpeg_mp3_to_wav(tmp_path, out_path)
            print(f"         → {out_path}")
        finally:
            os.unlink(tmp_path)

    print("Done. Copy seismoguard/response/audio/ to the robot.")


if __name__ == "__main__":
    main()
