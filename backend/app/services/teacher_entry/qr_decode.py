"""WeChat-style QR code decoder for teacher-entry images.

招聘海报底部那个"扫码投递"二维码 — OCR 看不见，但 cv2.wechat_qrcode（腾讯
自家模型）能直接 decode，包括中间嵌 logo 的微信样式 QR。

设计选择：
- 用 cv2.wechat_qrcode 而不是通用 cv2.QRCodeDetector 或 pyzbar：
  实测 7/9 vs 5/9 命中率，因为腾讯模型针对带 logo 的微信 QR 训练过。
- 极长截图（h/w > 3，常见于公众号截屏拼接）走切片重试：
  detector 对极端长宽比扫不出 → 按高度切成 ~正方形块再扫。
- 黑名单过滤公众号关注码（weixin.qq.com/r/...）— 这种是"关注此公众号"，
  不是投递链接，给学生填进去毫无用处。
- 单例懒加载：模型 ~1MB，首次 init ~50ms，后续免费。
- 模型不可用时静默返回 [] — 教师录入还能正常走 OCR/LLM 路径，不报错。
"""

from __future__ import annotations

import logging
import re
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_MODELS_DIR = Path(__file__).parent / 'wechat_qr_models'
_MODEL_FILES = ('detect.prototxt', 'detect.caffemodel', 'sr.prototxt', 'sr.caffemodel')

# 公众号关注 / 小程序跳转 / OAuth / 在线会议 — 一律不当投递链接。
# 会议类（teams / 腾讯会议 / VooV / 飞书 / 钉钉 / Zoom / Webex）经常出现在
# "线上宣讲会"海报下方，QR 一扫到就误填进 detail_url，学生点了进会议室
# 不知道怎么投递 — 比公众号关注码更糟。
_BLACKLIST_RE = re.compile(
    r'^https?://(?:'
    r'weixin\.qq\.com/r/|'                            # 公众号关注码
    r'mp\.weixin\.qq\.com/mp/profile_ext|'            # 公众号 profile
    r'open\.weixin\.qq\.com/connect/|'                # 微信 OAuth
    r'teams\.microsoft(?:online)?\.(?:com|cn)/l/meetup-join|'  # MS Teams 会议
    r'(?:meeting|vc)\.tencent\.com/|'                 # 腾讯会议
    r'voovmeeting\.com/|'                             # VooV (腾讯会议海外)
    r'(?:meeting|vc)\.feishu\.cn/|'                   # 飞书会议
    r'meeting\.dingtalk\.com/|'                       # 钉钉会议
    r'zoom\.us/j/|'                                   # Zoom join
    r'webex\.com/meet/'                               # Webex
    r')',
    re.IGNORECASE,
)

_lock = threading.Lock()
_detector: Optional[object] = None
_init_failed = False


def _get_detector():
    """Lazy singleton — first call ~50ms, subsequent calls free."""
    global _detector, _init_failed
    if _init_failed:
        return None
    if _detector is not None:
        return _detector
    with _lock:
        if _detector is not None:
            return _detector
        try:
            import cv2  # type: ignore
            for f in _MODEL_FILES:
                path = _MODELS_DIR / f
                if not path.exists():
                    raise FileNotFoundError(f'wechat_qr model missing: {path}')
            _detector = cv2.wechat_qrcode.WeChatQRCode(  # type: ignore[attr-defined]
                str(_MODELS_DIR / 'detect.prototxt'),
                str(_MODELS_DIR / 'detect.caffemodel'),
                str(_MODELS_DIR / 'sr.prototxt'),
                str(_MODELS_DIR / 'sr.caffemodel'),
            )
            logger.info('wechat_qrcode detector initialised')
        except Exception as exc:
            _init_failed = True
            logger.warning('wechat_qrcode init failed (QR decode disabled): %s', exc)
            return None
    return _detector


def decode_qr_urls(img_bytes: bytes) -> list[str]:
    """Decode QR codes in an image, return filtered, deduped http(s) URLs.

    Empty list = no QR found / no useful URLs / detector unavailable.
    保留输入顺序：第一次扫到的链接排在前面（通常 = 海报最显眼那个 QR）。
    """
    detector = _get_detector()
    if detector is None:
        return []

    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return []

    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return []

    h, w = img.shape[:2]
    if h == 0 or w == 0:
        return []

    found: list[str] = []
    seen: set[str] = set()

    def _accept(decoded_iter):
        for d in decoded_iter or []:
            d = (d or '').strip()
            if not d or not (d.startswith('http://') or d.startswith('https://')):
                continue
            if _BLACKLIST_RE.match(d):
                continue
            if d in seen:
                continue
            seen.add(d)
            found.append(d)

    # Pass 1：原图整张扫
    try:
        decoded, _points = detector.detectAndDecode(img)  # type: ignore[attr-defined]
        _accept(decoded)
    except Exception as exc:
        logger.warning('wechat_qrcode pass-1 decode failed: %s', exc)

    # Pass 2：极长截图（公众号拼图常见）切片再扫，detector 对极端长宽比识别率断崖
    if h > 3 * w:
        slice_h = w
        overlap = min(200, slice_h // 4)
        stride = slice_h - overlap

        # 自适应上限：保证滑窗能跑完整张图，再多 2 片冗余防漏；
        # 仍设硬上限 40 防对抗性输入（40 × 1080 stride ≈ 43200px 高，远超真实场景）
        max_slices = min(40, (h + stride - 1) // stride + 2)

        y = 0
        slice_count = 0
        last_end = 0
        while y < h and slice_count < max_slices:
            end = min(y + slice_h, h)
            crop = img[y:end, :]
            try:
                decoded, _points = detector.detectAndDecode(crop)  # type: ignore[attr-defined]
                _accept(decoded)
            except Exception:
                pass
            last_end = end
            if end == h:
                break
            y += stride
            slice_count += 1

        # Pass 3：保底贴底切片 — 滑窗若没让最后一片吃满 slice_h（QR 落在
        # h-slice_h:h 范围内时容易被切成"窄条"而 detector 识别不出），
        # 强制再扫一片以图底为基准的完整 slice_h 高度。
        # 559 广州期货那种 1080×15867、QR 在右下角的图被这一片救回。
        if last_end < h or (h - last_end) < slice_h:
            bottom_start = max(0, h - slice_h)
            if bottom_start != (last_end - slice_h):  # 避免和最后一片重复
                bottom_crop = img[bottom_start:h, :]
                try:
                    decoded, _points = detector.detectAndDecode(bottom_crop)  # type: ignore[attr-defined]
                    _accept(decoded)
                except Exception:
                    pass

    return found


def qr_decode_available() -> bool:
    """Cheap readiness probe."""
    return _get_detector() is not None
