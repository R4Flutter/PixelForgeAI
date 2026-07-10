# PixelForgeAI

Production-ready image processing pipeline + desktop GUI, built for Python 3.14.

Turns raw artwork into print-ready 4000×4000 transparent PNGs in one click —
background removal, AI upscaling for photos, and print-safe resizing — for
print-on-demand, Etsy, Shopify, and Amazon sellers.

## Pipeline Flow
```
Input Image → Background Removal → AI Upscale (photos only)
            → Resize to final width → Final Output (PNG / JPG / WebP)
```

The AI scripts in `scripts/` are a sealed black box. The GUI never calls them
directly — `backend/connector.py` patches `pipeline.CFG` and delegates to
`process_single_image` per image, then packages the final PNG into the
requested container. No AI source is modified.

## Features
- Background removal (rembg / U²-Net)
- AI upscaling (Upscayl / Real-ESRGAN), photos only — line-art is skipped
- Print-safe resizing (LANCZOS) to 2000 / 4000 / 6000 px
- Output as PNG (transparent), JPG, or WebP
- Batch processing with pause / resume / cancel
- Resume-safe (skip existing files via `overwrite=false`)
- PySide6 desktop app: drag & drop, live progress, log console
- Ed25519-signed offline licence + 7-day, machine-locked, anti-reset trial
- Placeholder auto-update check
- Logging for debugging

## Folder Structure
```
ai_image_pipeline/
├── app.py                 # GUI entry point
├── gui/                   # pages + main window (Qt presentation)
├── components/            # reusable themed widgets
├── themes/                # dark.qss design system
├── backend/               # connector / worker / job / state / license / updater
├── scripts/               # the AI pipeline (DO NOT EDIT)
├── assets/                # logo.svg
├── models/                # RealESRGAN_x4plus.pth
├── input/original/        # drop images here for the CLI
├── output/final/          # processed results
├── config/settings.yaml   # backend defaults
├── packaging/             # PyInstaller spec + Inno Setup installer
├── requirements.txt       # backend (AI) deps
└── requirements-gui.txt   # PySide6
```

## Setup
```bash
python -m venv venv
venv\Scripts\activate           # Windows  (source venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
pip install -r requirements-gui.txt
```

## Run the GUI
```bash
python app.py
```
The app loads `themes/dark.qss`, restores settings from the OS config dir, and
opens on the Home page. Drag images in (or Browse), pick an output size on the
Settings page, and hit **Process**. Progress, logs, pause/resume/cancel, and a
completion summary all live in-app.

## Run the pipeline (headless CLI)
```bash
python -m scripts.pipeline
```
This processes every image in `input/original/` using `config/settings.yaml`
defaults and writes to `output/final/`.

## Settings & Licence
Settings are persisted per-user in:
- Windows: `%APPDATA%\PixelForgeAI\settings.json`
- macOS:   `~/Library/Application Support/PixelForgeAI/settings.json`
- Linux:   `~/.config/PixelForgeAI/settings.json`

### Trial → licensed model
- **7-day free trial**, machine-locked and anti-reset, starts on first launch.
  The trial runs the **full** pipeline with no limits — it is simply
  time-boxed. Two HMAC-sealed copies of the start timestamp (an anchor plus a
  neutral-name witness) defeat casual reset; deleting only the obvious file is
  detected and the trial fails *closed* (expired), never silently reset.
- After expiry, processing is disabled until a licence key is entered; the app
  shows a professional **Trial ended** activation dialog, and activation is
  also available any time from the Settings page.
- A paid licence is a **$49 one-time, lifetime, offline** key (V1.x only).
  Keys are **Ed25519-signed** — the app bundles only the **public** half, so it
  can *verify* a key but never *forge* one. The activation record is
  HMAC-sealed and machine-bound, so it can't be hand-edited or copied
  machine-to-machine. (See `backend/license.py`, `backend/trial.py`,
  `backend/entitlement.py`.)
- The footer shows `Pro`, `Trial · Nd left`, or `Trial expired`.
- The Lemon Squeezy fulfilment path is stubbed in
  `backend/license_config.py` and activated by populating the checkout URL/API
  key; until then, V1 keys are minted offline with `tools/keygen.py`:

```bash
python tools/keygen.py --owner "Jane Buyer <jane@example.com>"
python tools/keygen.py --verify PFAI1.<payload>.<signature>
```

> `tools/keys/license_priv.pem` (the signing **private** key) is git-ignored
> and never bundled into a shipped build. On the developer's machine, the
> Settings page's **Generate test key** button mints a real signed key for
> testing; in a packaged build that button is hidden (no private key present).

## Packaging (Windows)
```bash
pyinstaller packaging/pixelforgeai.spec --noconfirm
# then, with Inno Setup installed:
iscc packaging\installer.iss
```
- `dist\PixelForgeAI\` — onedir build (folder install; extract-once for the
  bundled model weights and rembg/onnxruntime data).
- `dist\installer\PixelForgeAI-Setup-1.0.0.exe` — Windows installer with
  desktop/start-menu shortcuts and an uninstaller.

Add `assets/logo.ico` and set `icon="assets/logo.ico"` in the spec to brand the
executable.
