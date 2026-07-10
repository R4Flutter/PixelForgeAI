from enum import Enum, auto


class OutputFormat(Enum):
    PNG = "png"
    JPG = "jpg"
    WEBP = "webp"
    TIFF = "tiff"

    @property
    def suffix(self) -> str:
        return f".{self.value}"


class QualityPreset(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ULTRA = "ultra"
    LOSSLESS = "lossless"


class UpscaleMode(Enum):
    OFF = "off"
    X2 = "x2"
    X4 = "x4"
    X8 = "x8"
    AUTO = "auto"


class BackgroundMode(Enum):
    TRANSPARENT = "transparent"
    WHITE = "white"
    CUSTOM = "custom"


class MetadataPolicy(Enum):
    STRIP = "strip"
    PRESERVE = "preserve"


class ConflictPolicy(Enum):
    OVERWRITE = "overwrite"
    SKIP = "skip"
    AUTO_RENAME = "auto_rename"


class FitMode(Enum):
    WIDTH_ONLY = "width_only"
    FIT = "fit"
    EXACT = "exact"


class DeviceMode(Enum):
    GPU = "gpu"
    CPU = "cpu"


class PipelineStage(Enum):
    LOAD = "load"
    REMOVE_BG = "remove_bg"
    UPSCALE = "upscale"
    RESIZE = "resize"
    SAVE = "save"

    @property
    def label(self) -> str:
        return _STAGE_LABELS[self]


_STAGE_LABELS = {
    PipelineStage.LOAD: "Loading",
    PipelineStage.REMOVE_BG: "Remove Background",
    PipelineStage.UPSCALE: "Upscaling",
    PipelineStage.RESIZE: "Resizing",
    PipelineStage.SAVE: "Saving",
}


class ProcessingStatus(Enum):
    QUEUED = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


class ImageKind(Enum):
    PHOTO = "photo"
    VECTOR = "vector"
    DESIGN = "design"


class SourceKind(Enum):
    FILES = "files"
    FOLDER = "folder"


class EntitlementState(Enum):
    LICENSED = "licensed"
    TRIAL = "trial"
    LOCKED = "locked"


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
