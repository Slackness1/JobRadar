class ResumeUploadError(ValueError):
    def __init__(self, message: str, code: str = 'RESUME_UPLOAD_ERROR') -> None:
        super().__init__(message)
        self.code = code
