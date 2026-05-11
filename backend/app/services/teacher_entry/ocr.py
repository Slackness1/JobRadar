"""Local OCR for teacher quick-entry — RapidOCR (ONNX runtime).

设计选择（见 chat 中分析）：
- RapidOCR = PaddleOCR 的 ONNX 版本，~10 MB 模型，CPU 跑 0.5–1.5s/张
- 全部本地推理，截图不出 VPS（教师场景常含学生敏感信息）
- 单例懒加载，避免每请求重建 onnxruntime session

依赖：rapidocr-onnxruntime（pip 一行）。模型首次启动从 GitHub 自动下载。
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_engine: Optional[object] = None
_init_failed = False


def _get_engine():
    """Lazy singleton — first call init ~0.2s, subsequent calls free."""
    global _engine, _init_failed
    if _init_failed:
        return None
    if _engine is not None:
        return _engine
    with _lock:
        if _engine is not None:
            return _engine
        try:
            from rapidocr_onnxruntime import RapidOCR  # type: ignore
            _engine = RapidOCR()
            logger.info('RapidOCR engine initialised')
        except Exception as exc:  # pip 包没装 / onnx runtime 不兼容 等
            logger.warning('RapidOCR init failed: %s', exc)
            _init_failed = True
            return None
    return _engine


def ocr_image(img_bytes: bytes) -> Optional[str]:
    """Return concatenated text from an image, or None if OCR is unavailable.

    返回 None 让调用方知道"OCR 引擎不可用，请粘贴文字或换种来源"，
    跟"OCR 跑了但识别不出文字"（→ 返回空字符串）区分开。
    """
    engine = _get_engine()
    if engine is None:
        return None
    try:
        result, _elapsed = engine(img_bytes)  # type: ignore[operator]
    except Exception as exc:
        logger.warning('RapidOCR inference failed: %s', exc)
        return None
    if not result:
        return ''
    # result: [(bbox, text, confidence), ...]
    lines = [str(item[1]).strip() for item in result if len(item) >= 2 and item[1]]
    return '\n'.join(lines)


def ocr_available() -> bool:
    """Cheap readiness check — used by /health-style endpoints if needed."""
    return _get_engine() is not None
