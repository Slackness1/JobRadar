"""Aliyun Lingmou Avatar session manager.

Creates a real-time digital-human session via the Lingmou ROA API. The response
contains `rtcParams` that the frontend SDK (`lm-avatar-chat-sdk`) uses to join
the WebRTC channel and render the avatar video.

The API is ROA-style (REST), not RPC:
  POST /openapi/chat/init/{projectId}?platform=webSDK&instanceId=...
  (empty body)

Signing uses Aliyun V3 (ACS3-HMAC-SHA256). For ROA, the canonical request
includes the path (with the percent-encoded project id) and the canonical
query string.

Docs: https://help.aliyun.com/zh/avatar/avatar-application/developer-reference/developer-guide-chat-avatar-session
API version: 2025-05-27
Signature ref: https://help.aliyun.com/zh/sdk/developer-reference/v3-request-structure-and-signature
SDK reference (for path/query shape): alibabacloud-lingmou20250527 client.create_chat_session_with_options
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import json
import uuid
from datetime import datetime, timezone
from urllib import parse as urlparse, request as urllib_request

from app import config

logger = logging.getLogger(__name__)

_HOST = 'lingmou.cn-beijing.aliyuncs.com'
_API_VERSION = '2025-05-27'
_ALGORITHM = 'ACS3-HMAC-SHA256'


class AvatarUnavailable(RuntimeError):
    pass


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac_sha256(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode('utf-8'), hashlib.sha256).digest()


def _percent_encode(value: str) -> str:
    # RFC 3986 — same charset Aliyun V3 uses for canonical query/path.
    return urlparse.quote(value, safe='-_.~')


def _canonical_query(params: dict[str, str]) -> str:
    # Sorted by key, each k=v percent-encoded, joined by &.
    items = sorted(params.items())
    return '&'.join(f'{_percent_encode(k)}={_percent_encode(v)}' for k, v in items)


def _build_authorization(
    *,
    method: str,
    canonical_uri: str,
    canonical_query: str,
    action: str,
    body_bytes: bytes,
    timestamp: str,
    nonce: str,
) -> dict[str, str]:
    body_sha256 = _sha256_hex(body_bytes)
    headers_to_sign = {
        'host': _HOST,
        'x-acs-action': action,
        'x-acs-content-sha256': body_sha256,
        'x-acs-date': timestamp,
        'x-acs-signature-nonce': nonce,
        'x-acs-version': _API_VERSION,
    }
    sorted_header_names = sorted(headers_to_sign.keys())
    canonical_headers = ''.join(
        f'{name}:{headers_to_sign[name]}\n' for name in sorted_header_names
    )
    signed_headers = ';'.join(sorted_header_names)

    canonical_request = '\n'.join([
        method,
        canonical_uri,
        canonical_query,
        canonical_headers,
        signed_headers,
        body_sha256,
    ])
    string_to_sign = f'{_ALGORITHM}\n{_sha256_hex(canonical_request.encode("utf-8"))}'

    signature = _hmac_sha256(
        config.ALIYUN_ACCESS_KEY_SECRET.encode('utf-8'),
        string_to_sign,
    ).hex()

    authorization = (
        f'{_ALGORITHM} '
        f'Credential={config.ALIYUN_ACCESS_KEY_ID},'
        f'SignedHeaders={signed_headers},'
        f'Signature={signature}'
    )

    return {
        'Host': _HOST,
        'x-acs-action': action,
        'x-acs-content-sha256': body_sha256,
        'x-acs-date': timestamp,
        'x-acs-signature-nonce': nonce,
        'x-acs-version': _API_VERSION,
        'Authorization': authorization,
    }


def create_avatar_session(*, platform: str = 'Web') -> dict:
    """Call Lingmou CreateChatSession and return the full rtcParams dict."""
    if not config.ALIYUN_ACCESS_KEY_ID or not config.ALIYUN_ACCESS_KEY_SECRET:
        raise AvatarUnavailable(
            'Aliyun AK/SK missing: set ALIYUN_ACCESS_KEY_ID and ALIYUN_ACCESS_KEY_SECRET'
        )
    if not config.AVATAR_PROJECT_ID:
        raise AvatarUnavailable('AVATAR_PROJECT_ID missing in .env.local')

    project_id = config.AVATAR_PROJECT_ID
    canonical_uri = f'/openapi/chat/init/{_percent_encode(project_id)}'

    query_params: dict[str, str] = {'platform': platform}
    if config.AVATAR_INSTANCE_ID:
        query_params['instanceId'] = config.AVATAR_INSTANCE_ID
    canonical_query = _canonical_query(query_params)

    body_bytes = b''
    timestamp = datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    nonce = uuid.uuid4().hex

    headers = _build_authorization(
        method='POST',
        canonical_uri=canonical_uri,
        canonical_query=canonical_query,
        action='CreateChatSession',
        body_bytes=body_bytes,
        timestamp=timestamp,
        nonce=nonce,
    )

    url = f'https://{_HOST}{canonical_uri}'
    if canonical_query:
        url = f'{url}?{canonical_query}'

    req = urllib_request.Request(url, data=body_bytes, headers=headers, method='POST')

    try:
        with urllib_request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode('utf-8'))
    except Exception as exc:
        error_body = ''
        if hasattr(exc, 'read'):
            error_body = exc.read().decode('utf-8', errors='replace')  # type: ignore[union-attr]
        logger.error('Lingmou CreateChatSession failed: %s %s', exc, error_body)
        raise AvatarUnavailable(f'Lingmou API error: {exc} {error_body}') from exc

    logger.warning('Lingmou CreateChatSession raw response: %s', json.dumps(result, ensure_ascii=False))

    data = result.get('Data') or result.get('data') or {}
    rtc_params = data.get('RtcParams') or data.get('rtcParams') or {}
    session_id = data.get('SessionId') or data.get('sessionId') or result.get('SessionId')
    avatar_assets = data.get('AvatarAssets') or data.get('avatarAssets')

    if not rtc_params:
        raise AvatarUnavailable(f'No rtcParams in response: {result}')

    # The SDK expects sessionId alongside rtcParams (passed as IAvatarInitConfig.sessionId).
    # We flatten everything into one dict the frontend can spread directly.
    out: dict = {**rtc_params}
    if session_id:
        out['sessionId'] = session_id
    if avatar_assets:
        out['avatarAssets'] = avatar_assets
    return out
