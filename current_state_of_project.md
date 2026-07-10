# PixelForgeAI — Current State of Project

## Project Purpose
Desktop image processing pipeline (PySide6) for print-on-demand sellers. Turns raw artwork into print-ready 4000×4000 transparent PNGs in one click.
Pipeline: `Input Image → Background Removal → AI Upscale (photos only) → Resize → Output (PNG/JPG/WebP)`

## Git Status
- Single commit: `6b249cc4` — "desktop all ready" (July 5, 2026), no branches
- `gui/splash.py` is untracked (not committed)

---

## ✅ Completed (Fully Wired + Functional)

### AI Pipeline (`scripts/`)
- **`pipeline.py`** — orchestrates full pipeline: resize→remove_bg→upscale (photos only)→final resize. `CFG` dict runtime-configurable via `backend/connector.py`
- **`remove_bg.py`** — multi-strategy background removal: solid color detection, line art removal, photo AI removal (rembg/U²-Net), poster/merch detection
- **`upscale.py`** — Lanczos upscaling via OpenCV with 60M-pixel safety limit
- **`resize.py`** — Pillow resize with 3 fit modes (width_only, fit, exact), atomic save

### Backend (`backend/`)
- **`connector.py`** — `PipelineConnector` orchestrates pipeline, patches `CFG` at runtime, handles 4 Flow presets, output conversions, conflict policies, atomic saves
- **`worker.py`** — `ProcessingWorker(QThread)` offloads pipeline from UI thread, emits progress/status/log/stage signals, pause/resume/cancel
- **`job.py`** — dataclasses: `Settings` (18 fields), `JobRequest`, `RunSummary`. Enums for all config options
- **`state.py`** — platform-aware paths, settings load/save with atomic write
- **`log_bridge.py`** — non-invasive logging handler, maps raw log records to friendly stage labels
- **`entitlement.py`** — combines license + trial into LICENSED/TRIAL/LOCKED states
- **`license.py`** — Ed25519-signed offline license verification with activate/deactivate/mint_test_key
- **`license_crypto.py`** — Ed25519 key codec, PFAI format (prefix.b64payload.b64signature)
- **`license_config.py`** — external knobs: edition, trial days, keys, Lemon Squeezy config
- **`trial.py`** — 7-day machine-locked trial with anchor+witness anti-tamper
- **`storage_crypto.py`** — HMAC-SHA256 sealed JSON storage, machine-bound
- **`updater.py`** — architecture ready, `RELEASE_FEED_URL` empty (always returns "up to date")
- **`keys/license_pub.pem`** — Ed25519 public key bundled in app

### GUI (`gui/`)
- **`main_window.py`** — 5-page QStackedWidget sidebar nav, crossfade animation, entitlement/trial-expired dialogs
- **`home.py`** — drag & drop DropZone, browse files/folder, PreviewGrid thumbnail selector, Process button
- **`processing.py`** — live progress bar, step indicator, elapsed/ETA, pause/resume/cancel, LogConsole
- **`success.py`** — completion summary (total/succeeded/failed/elapsed), open output folder, process again
- **`settings_page.py`** — comprehensive settings: 4 preset cards, output/quality/compute/license sections
- **`splash.py`** — frameless branded launch with animated cubic Bezier path field, letter-by-letter title, Enter button (untracked)
- **`about.py`** — version info, publisher, website, support email
- **`trial_expired.py`** — activation dialog with key entry, owner, activate/buy/close

### Components (`components/`)
- **`buttons.py`** — PrimaryButton, SecondaryButton, DangerButton, GhostButton, IconButton, NavButton
- **`cards.py`** — SectionCard, StatCard, NavCard, ImageCard, DropZone (recursive folder expansion, 5K dir/20K img cap), PreviewGrid
- **`progress.py`** — ProgressBar, Throbber, StepIndicator, FeatureStepRail, LogConsole (4000-block cap)
- **`icons.py`** — ~35 programmatic SVG line-art icons (no asset files), color/accent substitution

### Packaging & Config
- **`packaging/pixelforgeai.spec`** — PyInstaller onedir build spec
- **`packaging/installer.iss`** — Inno Setup installer with shortcuts + uninstaller
- **`config/settings.yaml`** — default pipeline CFG values
- **`themes/dark.qss`** — 772-line dark design system with tokens, all widget types styled
- **`assets/logo.svg`** — brand logo (indigo→violet→magenta gradient, 160×160)
- **`models/RealESRGAN_x4plus.pth`** — ~64MB AI upscale model weights
- **`app.py`** — entry point: QApplication → load QSS → splash → main window

### Tools
- **`tools/keygen.py`** — offline Ed25519 license key generator (dev only, requires private key not in repo)

---

## ❌ Incomplete / Placeholder / Stubbed

### 1. Auto-Update — `backend/updater.py`
- `RELEASE_FEED_URL = ""` — empty string, check always returns "up to date"
- Architecture is ready (UpdateChecker class), needs a real release feed URL

### ✅ Splash Screen — Updated
- Removed Home, Enter, and Premium buttons from splash
- Added 5-second auto-transition timer → fades out and opens MainWindow
- Keyboard (Return/Space/Escape) still triggers early transition
- See `gui/splash.py`

### 2. Lemon Squeezy Storefront — `backend/license_config.py`
- `LS_CHECKOUT_URL`, `LS_API_KEY`, `LS_PRODUCT_ID` — all empty strings
- "Buy Now" button is disabled with "available soon" tooltip
- No e-commerce fulfillment wired — offline PFAI keys work, but no pay-to-license flow

### 3. Windows Icon — `packaging/pixelforgeai.spec` line 77
- `icon=None` with comment "Provide assets/logo.ico when ready"
- Packaged exe uses default Python rocket icon
- Needs `assets/logo.ico` created from `assets/logo.svg`

### 4. Splash Screen Untracked — `gui/splash.py`
- File exists and is fully functional (613 lines) but never committed
- Needs `git add gui/splash.py && git commit`

### 5. Premium Button Placeholder — `gui/splash.py:406-409`
- "Premium" button on splash screen just triggers same `enter_app()` handler
- Placeholder for future premium flow

---

## ⚠️ Known Issues / Concerns

| Issue | Location | Details |
|-------|----------|---------|
| Qt resource path | `settings_page.py:131` | `QPixmap(':/svg/check.svg')` references Qt resource but no `.qrc` file defined — may break |
| Image suffix mismatch | `scripts/pipeline.py:211` vs `backend/job.py:19` | Pipeline supports only `.png,.jpg,.jpeg,.webp`; job.py also lists `.bmp,.tif,.tiff` |
| Model loaded at import | `scripts/remove_bg.py:54` | `AI_SESSION = new_session()` loads rembg model eagerly — slows startup |
| No tests | entire project | Zero tests anywhere |
| No pyproject.toml | root | Uses old-school `requirements.txt` only |
| Single commit | git history | No incremental history, can't track changes |
| Untracked venvs | `.venv-linux/`, `venv310/` | Modified/incomplete virtual environments in untracked files |

---

## Architecture Layers

```
app.py
  └─ gui/         (PySide6 pages: splash, home, processing, success, settings, about)
      └─ components/  (reusable widgets: buttons, cards, progress, icons)
          └─ backend/     (Qt-agnostic: connector, worker, license, trial, state)
              └─ scripts/     (AI pipeline: remove_bg, upscale, resize)
```

## Key Files Reference

| File | Lines | Role |
|------|-------|------|
| `app.py` | ~1 | Entry point |
| `gui/main_window.py` | 358 | Main window with sidebar nav |
| `gui/settings_page.py` | 766 | Full settings form |
| `gui/splash.py` | 613 | Animated splash screen (untracked) |
| `gui/home.py` | 153 | Drag-drop + preview |
| `gui/processing.py` | 245 | Progress UI |
| `gui/success.py` | 160 | Completion results |
| `backend/connector.py` | 559 | Pipeline orchestrator |
| `backend/worker.py` | 102 | QThread worker |
| `backend/job.py` | 339 | Dataclasses + enums |
| `backend/entitlement.py` | 96 | License + trial state |
| `backend/license.py` | 205 | Ed25519 license system |
| `backend/license_config.py` | 114 | External knobs/config |
| `backend/trial.py` | 108 | 7-day trial with anti-tamper |
| `backend/updater.py` | 92 | Update checker (stub) |
| `components/cards.py` | 412 | DropZone, PreviewGrid, cards |
| `components/progress.py` | 441 | Progress bars, step indicator, log |
| `components/icons.py` | 199 | Inline SVG icons |
| `scripts/pipeline.py` | 235 | Pipeline orchestration |
| `scripts/remove_bg.py` | 1184 | Background removal (multi-strategy) |
| `scripts/upscale.py` | 186 | Lanczos upscaling |
| `scripts/resize.py` | 274 | Pillow resizing |
| `themes/dark.qss` | 772 | Dark theme stylesheet |
| `packaging/pixelforgeai.spec` | ~80 | PyInstaller spec |
| `packaging/installer.iss` | ~70 | Inno Setup script |



/epic-design https://www.awwwards.com/inspiration/home-il-capo use this page transition from home.py when i
click on precoess then page transition then procession of image will done once done then again page transition
and then result of image do this properly