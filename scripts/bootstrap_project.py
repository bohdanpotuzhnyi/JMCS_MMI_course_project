from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import urllib.request
import urllib.error
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = REPO_ROOT / ".venv"
REQUIREMENTS_FILE = REPO_ROOT / "requirements.txt"
GESTURE_MODEL_PATH = REPO_ROOT / "src" / "modalities" / "gesture" / "models" / "hand_landmarker.task"
VOSK_MODEL_DIR = REPO_ROOT / "src" / "modalities" / "voice" / "models" / "vosk-model"
VOSK_MODEL_INFO_PATH = VOSK_MODEL_DIR / ".model-id"

MEDIAPIPE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)
VOSK_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22-lgraph.zip"
VOSK_EXTRACTED_DIRNAME = "vosk-model-en-us-0.22-lgraph"


def _venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _venv_pip() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "pip.exe"
    return VENV_DIR / "bin" / "pip"


def ensure_venv() -> None:
    if VENV_DIR.exists():
        print(f"[setup] Reusing virtual environment: {VENV_DIR}")
        return

    print(f"[setup] Creating virtual environment: {VENV_DIR}")
    subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)


def install_requirements() -> None:
    pip_path = _venv_pip()
    print("[setup] Upgrading pip")
    subprocess.run([str(_venv_python()), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    print("[setup] Installing Python dependencies")
    subprocess.run([str(pip_path), "install", "-r", str(REQUIREMENTS_FILE)], check=True)


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"[setup] Downloading {url}")
    try:
        with urllib.request.urlopen(url) as response, destination.open("wb") as fh:
            shutil.copyfileobj(response, fh)
        return
    except urllib.error.URLError as exc:
        print(f"[setup] urllib download failed: {exc}")

    if shutil.which("curl"):
        subprocess.run(["curl", "-L", url, "-o", str(destination)], check=True)
        return

    if os.name == "nt":
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Invoke-WebRequest -Uri '{url}' -OutFile '{destination}'",
            ],
            check=True,
        )
        return

    raise RuntimeError(f"Could not download {url}. Neither urllib nor curl succeeded.")


def ensure_mediapipe_model() -> None:
    if GESTURE_MODEL_PATH.exists():
        print(f"[setup] Reusing MediaPipe hand model: {GESTURE_MODEL_PATH}")
        return
    download_file(MEDIAPIPE_MODEL_URL, GESTURE_MODEL_PATH)


def ensure_vosk_model() -> None:
    model_marker = VOSK_MODEL_DIR / "am"
    current_model_id = VOSK_MODEL_INFO_PATH.read_text(encoding="utf-8").strip() if VOSK_MODEL_INFO_PATH.exists() else ""
    if model_marker.exists() and current_model_id == VOSK_EXTRACTED_DIRNAME:
        print(f"[setup] Reusing Vosk model: {VOSK_MODEL_DIR}")
        return

    if VOSK_MODEL_DIR.exists():
        print(f"[setup] Replacing existing Vosk model with {VOSK_EXTRACTED_DIRNAME}")
        shutil.rmtree(VOSK_MODEL_DIR)

    archive_path = REPO_ROOT / "tmp-vosk-model.zip"
    download_file(VOSK_MODEL_URL, archive_path)

    extract_dir = REPO_ROOT / "src" / "modalities" / "voice" / "models"
    extract_dir.mkdir(parents=True, exist_ok=True)

    print(f"[setup] Extracting Vosk model to {extract_dir}")
    with zipfile.ZipFile(archive_path, "r") as zf:
        zf.extractall(extract_dir)
    archive_path.unlink(missing_ok=True)

    extracted = extract_dir / VOSK_EXTRACTED_DIRNAME
    if extracted.exists():
        if VOSK_MODEL_DIR.exists():
            shutil.rmtree(VOSK_MODEL_DIR)
        extracted.rename(VOSK_MODEL_DIR)
        VOSK_MODEL_INFO_PATH.write_text(VOSK_EXTRACTED_DIRNAME + "\n", encoding="utf-8")


def write_env_files() -> None:
    env_map = {
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "VOSK_MODEL_PATH": str(VOSK_MODEL_DIR),
        "MEDIAPIPE_HAND_MODEL_PATH": str(GESTURE_MODEL_PATH),
    }

    sh_lines = [
        f'export {key}="{value}"'
        for key, value in env_map.items()
    ]
    (REPO_ROOT / ".project-env.sh").write_text("\n".join(sh_lines) + "\n", encoding="utf-8")

    ps_lines = [
        f'$env:{key} = "{value}"'
        for key, value in env_map.items()
    ]
    (REPO_ROOT / ".project-env.ps1").write_text("\n".join(ps_lines) + "\n", encoding="utf-8")

    cmd_lines = [
        f"set {key}={value}"
        for key, value in env_map.items()
    ]
    (REPO_ROOT / ".project-env.cmd").write_text("\n".join(cmd_lines) + "\n", encoding="utf-8")

    print("[setup] Wrote environment helper files: .project-env.sh, .project-env.ps1, .project-env.cmd")


def print_next_steps() -> None:
    print("")
    print("[setup] Complete.")
    print(f"[setup] Python: {_venv_python()}")
    print(f"[setup] Vosk model: {VOSK_MODEL_DIR}")
    print(f"[setup] MediaPipe model: {GESTURE_MODEL_PATH}")
    print("")
    if os.name == "nt":
        print("Activate with one of:")
        print(r"  . .\scripts\activate_windows.ps1")
        print(r"  scripts\activate_windows.bat")
    else:
        print("Activate with:")
        print("  source scripts/activate_macos.sh")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap the multimodal toolkit project.")
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip pip installation and only ensure models/env files.",
    )
    parser.add_argument(
        "--skip-model-downloads",
        action="store_true",
        help="Skip model downloads and only generate env files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_venv()
    if not args.skip_install:
        install_requirements()
    if not args.skip_model_downloads:
        ensure_mediapipe_model()
        ensure_vosk_model()
    write_env_files()
    print_next_steps()


if __name__ == "__main__":
    main()
