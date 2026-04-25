from io import BytesIO

from app import config
from app.services.resume_copilot import ResumeUploadError

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - covered once dependency is installed
    PdfReader = None


def extract_resume_text_from_pdf(file_bytes: bytes) -> str:
    text, _ = extract_resume_text_with_page_count(file_bytes)
    return text


def extract_resume_text_with_page_count(file_bytes: bytes) -> tuple[str, int]:
    if not file_bytes:
        raise ResumeUploadError("Resume upload was empty")

    max_upload_bytes = config.RESUME_COPILOT_MAX_UPLOAD_MB * 1024 * 1024
    if len(file_bytes) > max_upload_bytes:
        raise ResumeUploadError(
            f"Resume upload exceeded {config.RESUME_COPILOT_MAX_UPLOAD_MB} MB limit"
        )

    if PdfReader is None:
        raise RuntimeError("pypdf is required for resume parsing")

    try:
        reader = PdfReader(BytesIO(file_bytes))
    except Exception as exc:
        raise ResumeUploadError("Resume file could not be parsed as PDF") from exc

    page_count = len(reader.pages)
    text_parts: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        page_text = page_text.strip()
        if page_text:
            text_parts.append(page_text)

    if not text_parts:
        raise ResumeUploadError("Resume file did not contain readable text")

    return "\n\n".join(text_parts), page_count


def validate_pdf_upload(filename: str, content_type: str) -> None:
    normalized_name = (filename or '').strip().lower()
    normalized_content_type = (content_type or '').strip().lower()

    if not normalized_name.endswith('.pdf'):
        raise ResumeUploadError('Only PDF resumes are supported', code='INVALID_FILE_TYPE')
    if normalized_content_type and 'pdf' not in normalized_content_type:
        raise ResumeUploadError('Only PDF resumes are supported', code='INVALID_FILE_TYPE')
