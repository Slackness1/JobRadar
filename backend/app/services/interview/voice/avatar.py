"""Aliyun Lingmou Avatar session manager.

Creates a real-time digital-human session via the Lingmou RPC API. The response
contains `rtcParams` that the frontend SDK (`lm-avatar-chat-sdk`) uses to join
the WebRTC channel and render the avatar video.

Docs: https://help.aliyun.com/zh/avatar/avatar-application/developer-reference/developer-guide-chat-avatar-session
API version: 2025-05-27
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone
from urllib import parse as urlparse, request as urllib_request

from app import config

logger = logging.getLogger(__name__)

_ENDPOINT = 'https://lingmou.cn-beijing.aliyuncs.com'


class AvatarUnavailable(RuntimeError):
    pass


def _percent_encode(value: str) -> str:
    return urlparse.quote(value, safe='~')


def _sign(params: dict[str, str], method: str = 'POST') -> str:
    canonical = '&'.join(
        f'{_percent_encode(k)}={_percent_encode(params[k])}'
        for k in sorted(params)
    )
    string_to_sign = f'{method}&%2F&{_percent_encode(canonical)}'
    key = (config.ALIYUN_ACCESS_KEY_SECRET + '&').encode('utf-8')
    digest = hmac.new(key, string_to_sign.encode('utf-8'), hashlib.sha1).digest()
    return base64.b64encode(digest).decode('utf-8')


def create_avatar_session(*, platform: str = 'webSDK') -> dict:
    """Call Lingmou CreateChatSession and return the full rtcParams dict."""
    if not config.ALIYUN_ACCESS_KEY_ID or not config.ALIYUN_ACCESS_KEY_SECRET:
        raise AvatarUnavailable(
            'Aliyun AK/SK missing: set ALIYUN_ACCESS_KEY_ID and ALIYUN_ACCESS_KEY_SECRET'
        )
    if not config.AVATAR_PROJECT_ID:
        raise AvatarUnavailable('AVATAR_PROJECT_ID missing in .env.local')

    common_params = {
        'Format': 'JSON',
        'Version': '2025-05-27',
        'AccessKeyId': config.ALIYUN_ACCESS_KEY_ID,
        'SignatureMethod': 'HMAC-SHA1',
        'SignatureVersion': '1.0',
        'SignatureNonce': uuid.uuid4().hex,
        'Timestamp': datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'Action': 'CreateChatSession',
    }

    body_params = {
        'Id': config.AVATAR_PROJECT_ID,
        'Platform': platform,
    }
    if config.AVATAR_INSTANCE_ID:
        body_params['InstanceId'] = config.AVATAR_INSTANCE_ID

    # Sign with common params only (body goes as POST form)
    common_params['Signature'] = _sign(common_params, method='POST')

    url = _ENDPOINT + '/?' + urlparse.urlencode(common_params)
    form_data = urlparse.urlencode(body_params).encode('utf-8')

    req = urllib_request.Request(
        url,
        data=form_data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )

    try:
        with urllib_request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode('utf-8'))
    except Exception as exc:
        error_body = ''
        if hasattr(exc, 'read'):
            error_body = exc.read().decode('utf-8', errors='replace')  # type: ignore[union-attr]
        logger.error('Lingmou CreateChatSession failed: %s %s', exc, error_body)
        raise AvatarUnavailable(f'Lingmou API error: {exc} {error_body}') from exc

    data = result.get('Data') or result.get('data') or {}
    rtc_params = data.get('RtcParams') or data.get('rtcParams') or data
    if not rtc_params:
        raise AvatarUnavailable(f'No rtcParams in response: {result}')

    return rtc_params
