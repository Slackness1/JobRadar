"""Aliyun NLS token provider.

NLS (Natural Language Service / 智能语音交互) gates realtime ASR + TTS behind
a short-lived token generated from your Access Key. We sign a CreateToken RPC
request, cache the result, and refresh a couple of minutes before expiry.

Docs: https://help.aliyun.com/zh/isi/getting-started/obtain-a-token
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib import parse as urlparse, request as urllib_request

from app import config

_NLS_META_HOST = 'http://nls-meta.cn-shanghai.aliyuncs.com/'
_REFRESH_SAFETY_SECONDS = 120  # refresh 2min before expiry


@dataclass
class NlsToken:
    token: str
    expires_at: float  # unix ts


class AliyunTokenError(RuntimeError):
    pass


def _percent_encode(value: str) -> str:
    return urlparse.quote(value, safe='~')


def _build_signature(params: dict[str, str], access_key_secret: str) -> str:
    canonical = '&'.join(
        f'{_percent_encode(k)}={_percent_encode(params[k])}'
        for k in sorted(params)
    )
    string_to_sign = 'GET&%2F&' + _percent_encode(canonical)
    key = (access_key_secret + '&').encode('utf-8')
    digest = hmac.new(key, string_to_sign.encode('utf-8'), hashlib.sha1).digest()
    return base64.b64encode(digest).decode('utf-8')


def _request_new_token() -> NlsToken:
    ak_id = config.ALIYUN_ACCESS_KEY_ID
    ak_secret = config.ALIYUN_ACCESS_KEY_SECRET
    if not ak_id or not ak_secret:
        raise AliyunTokenError(
            'Aliyun credentials missing: set ALIYUN_ACCESS_KEY_ID and '
            'ALIYUN_ACCESS_KEY_SECRET in backend/.env.local'
        )

    params = {
        'AccessKeyId': ak_id,
        'Action': 'CreateToken',
        'Format': 'JSON',
        'RegionId': config.ALIYUN_NLS_REGION or 'cn-shanghai',
        'SignatureMethod': 'HMAC-SHA1',
        'SignatureNonce': uuid.uuid4().hex,
        'SignatureVersion': '1.0',
        'Timestamp': datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'Version': '2019-02-28',
    }
    params['Signature'] = _build_signature(params, ak_secret)

    url = _NLS_META_HOST + '?' + urlparse.urlencode(params)
    req = urllib_request.Request(url, method='GET')
    with urllib_request.urlopen(req, timeout=10) as resp:
        body = json.loads(resp.read().decode('utf-8'))

    token_info = body.get('Token') or {}
    token_id = token_info.get('Id')
    expire_time = token_info.get('ExpireTime')
    if not token_id or not expire_time:
        raise AliyunTokenError(f'Unexpected Aliyun response: {body}')
    return NlsToken(token=str(token_id), expires_at=float(expire_time))


class TokenCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current: NlsToken | None = None

    def get(self) -> str:
        with self._lock:
            if self._current and self._current.expires_at - _REFRESH_SAFETY_SECONDS > time.time():
                return self._current.token
            self._current = _request_new_token()
            return self._current.token


_cache = TokenCache()


def get_token() -> str:
    """Return a currently-valid NLS token. Raises AliyunTokenError if unconfigured."""
    return _cache.get()
