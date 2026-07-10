class PipelineError(Exception):
    pass


class ValidationError(PipelineError):
    pass


class ImageLoadError(PipelineError):
    pass


class ProcessingError(PipelineError):
    pass


class ExportError(PipelineError):
    pass


class CancelledError(PipelineError):
    pass


class ConfigurationError(PipelineError):
    pass


class EntitlementError(PipelineError):
    pass
