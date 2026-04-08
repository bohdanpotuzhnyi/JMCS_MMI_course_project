# Setup Scripts

## macOS / Linux

Run:

```bash
./scripts/setup_macos.sh
source scripts/activate_macos.sh
```

## Windows PowerShell

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
. .\scripts\activate_windows.ps1
```

## Windows cmd.exe

After setup in PowerShell, activate with:

```bat
scripts\activate_windows.bat
```

## What the setup does

- creates `.venv` if missing
- installs `requirements.txt`
- downloads the MediaPipe hand model
- downloads and extracts the larger dynamic-graph English Vosk model (`vosk-model-en-us-0.22-lgraph`)
- writes shell-specific environment helper files for `PYTHONPATH`, `VOSK_MODEL_PATH`, and `MEDIAPIPE_HAND_MODEL_PATH`
