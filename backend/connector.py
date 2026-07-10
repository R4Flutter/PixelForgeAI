"""
connector.py
------------
PipelineConnector - the integration layer between the GUI and the EXISTING,
untouched AI backend.

Design contract (must never be broken):
  * It does NOT reimplement, wrap, or modify any AI logic.
  * The only thing it touches in ``scripts.pipeline`` is the module-level
    runtime config dict ``pipeline.CFG`` - patching its values at runtime to
    honour the user's selected input/output/final-size, exactly as the dict is
    intended to be used. No source file in scripts/ is edited.
  * Per-image work is delegated to the backend's own ``process_single_image``.
  * The single piece of post-processing (PNG -> JPG/WebP container format) is
    output packaging, not AI: it only re-encodes the backend's already-final
    PNG. It lives here, never in scripts/.

The connector is Qt-agnostic: it communicates purely through callback hooks.
``backend.worker`` adapts those callbacks to Qt signals, keeping this module
importable and unit-testable without PySide6 installed.
"""

from __future__ import annotations

import os
import shutil
import threading
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from PIL import Image, ImageColor

from backend.job import (
    BackgroundMode,
    ConflictPolicy,
    DeviceMode,
    FitMode,
    JobRequest,
    MAX_OUTPUT_DIM,
    MetadataPolicy,
    MIN_OUTPUT_DIM,
    OutputFormat,
    QualityPreset,
    RunSummary,
    Settings,
    UpscaleMode,
)
from backend.log_bridge import LogBridge, StageMapper
from backend.state import paths

# Optional / late backend imports - resolved lazily so a missing AI dependency
# produces a clean, catchable error rather than an import-time crash.
try:
    from scripts import pipeline as _pipeline  # type: ignore
except Exception as exc:  # pragma: no cover - environment dependent
    _pipeline = None  # type: ignore
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


class ConnectorError(RuntimeError):
    """Raised when the existing backend cannot be reached."""


# --------------------------------------------------------------------------- #
# Callback hooks injected by the UI/worker. Defaults are no-ops.              #
# --------------------------------------------------------------------------- #
@dataclass
class Callbacks:
    on_stage: Callable[[str], None] = lambda stage: None
    on_status: Callable[[str], None] = lambda text: None
    on_progress: Callable[[int, int, str], None] = lambda done, total, file: None
    on_log: Callable[[str, str, str], None] = lambda level, logger, message: None
    on_image_failed: Callable[[str, str], None] = lambda name, message: None


@dataclass
class _CfgSnapshot:
    """Captured pipeline.CFG entries restored after the run."""
    values: Dict[str, object] = field(default_factory=dict)


class PipelineConnector:
    """Orchestrates one job against the existing AI backend."""

    POLL_INTERVAL = 0.1

    def __init__(self, callbacks: Callbacks | None = None) -> None:
        self.cb = callbacks or Callbacks()
        self._stage = StageMapper()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def validate_backend(self) -> None:
        if _pipeline is None:
            raise ConnectorError(
                "AI backend (scripts.pipeline) could not be imported. "
                f"Install the backend dependencies: {_IMPORT_ERROR!r}"
            )

    def run(
        self,
        job: JobRequest,
        pause_event: threading.Event,
        cancel_event: threading.Event,
    ) -> RunSummary:
        """Execute a job honouring pause/cancel. Never raises on per-image
        failure - those are captured in the returned RunSummary."""
        self.validate_backend()

        images = job.resolve_image_paths()
        total = len(images)
        if total == 0:
            return RunSummary(total=0, succeeded=0, failed=0, elapsed_seconds=0.0)

        job.settings.output_folder = self._resolved_output(job.settings.output_folder)
        self._ensure_writable_output(Path(job.settings.output_folder))

        self._apply_device_hint(job.settings.device)
        snapshot = self._patch_cfg(job.settings)

        bridge = LogBridge(
            sink=lambda level, name, msg: self._on_log_record(level, name, msg)
        ).install()

        start = time.monotonic()
        succeeded = 0
        failed_files: List[str] = []
        try:
            self.cb.on_progress(0, total, "")
            self._stage.reset()
            self.cb.on_stage(StageMapper.DEFAULT_STAGE)

            for image_path in images:
                if self._await_pause_or_cancel(pause_event, cancel_event):
                    break  # cancelled while paused

                if cancel_event.is_set():
                    break

                img_str = str(image_path)
                self.cb.on_status(img_str)
                if self._should_skip_existing(Path(image_path), job.settings):
                    succeeded += 1
                    self.cb.on_log(
                        "INFO", "PIXELFORGE",
                        f"Skipped existing output: {Path(image_path).name}",
                    )
                    self.cb.on_progress(succeeded + len(failed_files), total,
                                        img_str)
                    continue

                try:
                    _pipeline.process_single_image(Path(image_path))
                    self._post_process(Path(image_path), job.settings)
                    succeeded += 1
                    self.cb.on_log("INFO", "PIXELFORGE",
                                   f"Completed: {Path(image_path).name}")
                except Exception as exc:  # backend raises PipelineError + others
                    failed_files.append(image_path.name)
                    self.cb.on_image_failed(img_str, str(exc))
                    self.cb.on_log("ERROR", "PIXELFORGE",
                                   f"Failed: {image_path.name} - {exc}")
                finally:
                    self.cb.on_progress(succeeded + len(failed_files), total,
                                        str(image_path))
        finally:
            bridge.uninstall()
            self._restore_cfg(snapshot)
            self._cleanup_work(job.settings)

        elapsed = time.monotonic() - start
        cancelled = cancel_event.is_set()
        return RunSummary(
            total=total,
            succeeded=succeeded,
            failed=len(failed_files),
            elapsed_seconds=elapsed,
            failed_files=tuple(failed_files),
            cancelled=cancelled,
        )

    # ------------------------------------------------------------------ #
    # Pause / cancel
    # ------------------------------------------------------------------ #
    def _await_pause_or_cancel(
        self,
        pause_event: threading.Event,
        cancel_event: threading.Event,
    ) -> bool:
        """Block while paused. Returns True if a cancel was requested."""
        while pause_event.is_set() and not cancel_event.is_set():
            time.sleep(self.POLL_INTERVAL)
        return cancel_event.is_set()

    # ------------------------------------------------------------------ #
    # Stage mapping from AI logs
    # ------------------------------------------------------------------ #
    def _on_log_record(self, level: str, name: str, message: str) -> None:
        self.cb.on_log(level, name, message)
        label = self._stage.map(message)
        if label:
            self.cb.on_stage(label)

    # ------------------------------------------------------------------ #
    # Runtime CFG patching (no edits to pipeline.py)
    # ------------------------------------------------------------------ #
    def _resolved_output(self, folder: str) -> str:
        if not folder or str(folder).strip() in ("", "."):
            return str((paths().root / "output" / "final").resolve())
        return str(Path(folder).expanduser().resolve())

    def _ensure_writable_output(self, folder: Path) -> None:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=str(folder), delete=False) as tmp:
                tmp_path = Path(tmp.name)
            tmp_path.unlink(missing_ok=True)
        except OSError as exc:
            raise ConnectorError(
                f"Output folder is not writable: {folder} ({exc})"
            ) from exc

    def _patch_cfg(self, settings: Settings) -> _CfgSnapshot:
        assert _pipeline is not None
        self._cleanup_work(settings)
        work = paths().work_dir
        work_resized = work / "resized"
        work_no_bg = work / "no_bg"
        work_upscaled = work / "upscaled"
        work_final = work / "final"
        for d in (work_resized, work_no_bg, work_upscaled, work_final):
            d.mkdir(parents=True, exist_ok=True)

        snapshot = _CfgSnapshot()
        width, height, fit = self._resolve_geometry(settings)
        upscale_factor = self._resolve_upscale_factor(settings)
        updates = {
            "output_resized": work_resized,
            "output_no_bg": work_no_bg,
            "output_upscaled": work_upscaled,
            "output_final": work_final,
            "final_size": width,
            "final_height": height,
            "fit_mode": fit.value,
            "png_compression": max(0, min(9, int(settings.png_compression or 6))),
            "upscale_factor": upscale_factor,
            "upscale_enabled": settings.upscale_mode is not UpscaleMode.OFF and upscale_factor > 1,
            "upscale_engine": "realesrgan",
            "upscale_model": "realesrgan-x4plus",
            "upscale_fallback": True,
            "upscale_timeout": 600,
            "overwrite": True,
        }
        for key, value in updates.items():
            if key in _pipeline.CFG:
                snapshot.values[key] = _pipeline.CFG[key]
                _pipeline.CFG[key] = value
        return snapshot

    def _resolve_geometry(
        self, settings: Settings
    ) -> Tuple[int, int, FitMode]:
        """Validate + clamp the user's resolution. Degrades fit/exact to
        width-only if a box height wasn't provided, so a bad persisted setting
        can never crash the run."""
        width = max(MIN_OUTPUT_DIM, min(MAX_OUTPUT_DIM, int(settings.output_width or 4000)))
        height = max(0, min(MAX_OUTPUT_DIM, int(settings.output_height or 0)))
        fit = settings.fit_mode if isinstance(settings.fit_mode, FitMode) else FitMode.WIDTH_ONLY
        if fit is not FitMode.WIDTH_ONLY and height < MIN_OUTPUT_DIM:
            self.cb.on_log(
                "WARNING", "PIXELFORGE",
                f"Fit/Exact mode needs a height >= {MIN_OUTPUT_DIM}px (got {height}). "
                "Falling back to width-only for this run.",
            )
            fit = FitMode.WIDTH_ONLY
            height = 0
        return width, height, fit

    @staticmethod
    def _resolve_upscale_factor(settings: Settings) -> int:
        mode = settings.upscale_mode
        if mode is UpscaleMode.OFF:
            return 1
        if mode is UpscaleMode.X2:
            return 2
        if mode is UpscaleMode.X8:
            return 8
        if mode is UpscaleMode.AUTO:
            width = int(settings.output_width or 4000)
            if width <= 3000:
                return 2
            if width <= 6000:
                return 4
            return 8
        return 4

    def _restore_cfg(self, snapshot: _CfgSnapshot) -> None:
        if _pipeline is None:
            return
        for key, value in snapshot.values.items():
            _pipeline.CFG[key] = value

    # ------------------------------------------------------------------ #
    # Output packaging: PNG -> requested container (not AI logic)
    # ------------------------------------------------------------------ #
    def _post_process(self, image_path: Path, settings: Settings) -> None:
        final_png = paths().work_dir / "final" / f"{image_path.stem}.png"
        if not final_png.exists() or final_png.stat().st_size == 0:
            raise ConnectorError(f"Backend did not produce a final image for {image_path.name}")

        target_path = self._resolve_target_path(image_path, settings)
        if target_path is None:
            return

        self._write_packaged_image(final_png, image_path, target_path, settings)
        try:
            final_png.unlink()
        except OSError:
            pass

    def _should_skip_existing(self, image_path: Path, settings: Settings) -> bool:
        if settings.conflict_policy is not ConflictPolicy.SKIP:
            return False
        return self._target_base_path(image_path, settings).exists()

    def _resolve_target_path(
        self, image_path: Path, settings: Settings
    ) -> Path | None:
        target = self._target_base_path(image_path, settings)
        if target.exists():
            if settings.conflict_policy is ConflictPolicy.SKIP:
                return None
            if settings.conflict_policy is ConflictPolicy.AUTO_RENAME:
                return self._unique_path(target)
        return target

    @staticmethod
    def _target_base_path(image_path: Path, settings: Settings) -> Path:
        return Path(settings.output_folder) / f"{image_path.stem}{settings.output_format.suffix}"

    @staticmethod
    def _unique_path(path: Path) -> Path:
        if not path.exists():
            return path
        for idx in range(1, 10_000):
            candidate = path.with_name(f"{path.stem} ({idx}){path.suffix}")
            if not candidate.exists():
                return candidate
        stamp = int(time.time())
        return path.with_name(f"{path.stem} ({stamp}){path.suffix}")

    def _write_packaged_image(
        self,
        src_png: Path,
        original: Path,
        dst: Path,
        settings: Settings,
    ) -> None:
        fmt = settings.output_format
        dst.parent.mkdir(parents=True, exist_ok=True)

        with Image.open(src_png) as im:
            im.load()
            out = self._compose_background(im, fmt, settings)
            save_format, save_kwargs = self._save_options(fmt, settings, original)
            self._atomic_save(out, dst, save_format, save_kwargs)

    def _compose_background(
        self, im: Image.Image, fmt: OutputFormat, settings: Settings
    ) -> Image.Image:
        wants_flat = settings.background_mode is not BackgroundMode.TRANSPARENT
        must_flatten = fmt is OutputFormat.JPG
        if not wants_flat and not must_flatten:
            return im.convert("RGBA") if im.mode not in ("RGBA", "RGB") else im.copy()

        bg = Image.new("RGB", im.size, self._background_rgb(settings, must_flatten))
        if im.mode in ("RGBA", "LA"):
            bg.paste(im, mask=im.split()[-1])
        else:
            bg.paste(im.convert("RGB"))
        return bg

    @staticmethod
    def _background_rgb(
        settings: Settings, forced_for_opaque_format: bool
    ) -> tuple[int, int, int]:
        if settings.background_mode is BackgroundMode.WHITE:
            return (255, 255, 255)
        if settings.background_mode is BackgroundMode.CUSTOM:
            try:
                return ImageColor.getrgb(settings.background_color)
            except ValueError:
                return (255, 255, 255)
        if forced_for_opaque_format:
            try:
                return ImageColor.getrgb(settings.jpg_background)
            except ValueError:
                return (255, 255, 255)
        return (255, 255, 255)

    def _save_options(
        self, fmt: OutputFormat, settings: Settings, original: Path
    ) -> tuple[str, Dict[str, object]]:
        jpg_q, webp_q, png_c, webp_lossless = self._effective_quality(settings)
        exif = (
            self._source_exif(original)
            if settings.metadata_policy is MetadataPolicy.PRESERVE
            else None
        )

        if fmt is OutputFormat.JPG:
            opts: Dict[str, object] = {"quality": jpg_q, "optimize": True}
            if exif:
                opts["exif"] = exif
            return "JPEG", opts
        if fmt is OutputFormat.WEBP:
            opts = {"quality": webp_q, "method": 6, "lossless": webp_lossless}
            if exif:
                opts["exif"] = exif
            return "WEBP", opts
        if fmt is OutputFormat.TIFF:
            opts = {"compression": "tiff_lzw"}
            if exif:
                opts["exif"] = exif
            return "TIFF", opts
        return "PNG", {"compress_level": png_c, "optimize": True}

    @staticmethod
    def _effective_quality(settings: Settings) -> tuple[int, int, int, bool]:
        preset = settings.quality_preset
        if preset is QualityPreset.LOW:
            return 70, 70, 9, False
        if preset is QualityPreset.MEDIUM:
            return 85, 82, 7, False
        if preset is QualityPreset.ULTRA:
            return 100, 98, 3, False
        if preset is QualityPreset.LOSSLESS:
            return 100, 100, 6, True
        return (
            max(1, min(100, int(settings.jpg_quality))),
            max(1, min(100, int(settings.webp_quality))),
            max(0, min(9, int(settings.png_compression))),
            False,
        )

    @staticmethod
    def _source_exif(path: Path) -> bytes | None:
        try:
            with Image.open(path) as im:
                exif = im.getexif()
                return exif.tobytes() if exif else None
        except OSError:
            return None

    @staticmethod
    def _atomic_save(
        image: Image.Image,
        dst: Path,
        save_format: str,
        save_kwargs: Dict[str, object],
    ) -> None:
        tmp_handle = tempfile.NamedTemporaryFile(
            dir=str(dst.parent), delete=False, suffix=dst.suffix
        )
        tmp_path = Path(tmp_handle.name)
        tmp_handle.close()
        try:
            image.save(tmp_path, save_format, **save_kwargs)
            if not tmp_path.exists() or tmp_path.stat().st_size == 0:
                raise ConnectorError(f"Packaged output is empty: {dst.name}")
            os.replace(tmp_path, dst)
        finally:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass

    # ------------------------------------------------------------------ #
    # Device hint (best-effort; backend is unchanged)
    # ------------------------------------------------------------------ #
    def _apply_device_hint(self, device: DeviceMode) -> None:
        # CPU path: hide CUDA so onnxruntime/torch fall back to CPU providers.
        # GPU path: leave defaults so libraries may use CUDA if installed.
        if device is DeviceMode.CPU:
            os.environ["CUDA_VISIBLE_DEVICES"] = ""
            self.cb.on_log("INFO", "PIXELFORGE",
                           "Device hint: CPU (CUDA hidden, best-effort).")
        else:
            os.environ.pop("CUDA_VISIBLE_DEVICES", None)
            self.cb.on_log("INFO", "PIXELFORGE",
                           "Device hint: GPU requested (best-effort, depends on "
                           "installed runtimes).")

    # ------------------------------------------------------------------ #
    # Work dir cleanup
    # ------------------------------------------------------------------ #
    def _cleanup_work(self, settings: Settings) -> None:
        work = paths().work_dir
        for sub in ("resized", "no_bg", "upscaled", "final"):
            target = work / sub
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
