"""跨厂商判官:Gemini(经 Google Code Assist 端点,复用 Antigravity 的 consumer OAuth 登录)。

为什么走这条:eval 判官必须跨厂商防 self-judge bias,但 mimo/dashscope key 已失效。
用户用 Antigravity 登录授权后,我们拿到带 refresh_token 的 consumer OAuth 凭据,经
cloudcode-pa.googleapis.com 的 Code Assist 端点调 Gemini —— 零 API key、access token
自动续期(refresh_token + gemini-cli 公开 client),真·跨厂商(Google)。

凭据文件(0600,VPS 本地,不入仓):GEMINI_OAUTH_CREDS env 指定,默认
/home/ubuntu/.config/jobradar-eval/gemini_oauth.json,形如:
  {access_token, refresh_token, token_type, scope, expiry_epoch, client_id, client_secret}
project 由 loadCodeAssist 拿一次后缓存进文件。

接口 .chat(messages, *, temperature, response_format, max_retries) -> str 与 eval 的
LLMClient 对齐,可直接塞进 build_judge_client。
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_DEFAULT_CREDS = "/home/ubuntu/.config/jobradar-eval/gemini_oauth.json"
_CODE_ASSIST_HOST = "cloudcode-pa.googleapis.com"
_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _opener() -> urllib.request.OpenerDirector:
    # 只走 http(s) 代理(dev 出网 127.0.0.1:7890);忽略 ALL_PROXY 的 socks(urllib 不支持)。
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or ""
    handlers = [urllib.request.ProxyHandler({"https": proxy, "http": proxy})] if proxy else [
        urllib.request.ProxyHandler({})
    ]
    return urllib.request.build_opener(*handlers)


@dataclass
class GeminiCodeAssistClient:
    creds_path: str = field(default_factory=lambda: os.environ.get("GEMINI_OAUTH_CREDS", _DEFAULT_CREDS))
    model: str = field(default_factory=lambda: os.environ.get("EVAL_JUDGE_MODEL_GEMINI", "gemini-2.5-flash"))
    timeout_seconds: int = 180
    label: str = "JUDGE(gemini)"
    _creds: dict | None = None

    def _load(self) -> dict:
        if self._creds is None:
            with open(self.creds_path) as f:
                self._creds = json.load(f)
        return self._creds

    def _save(self) -> None:
        if self._creds is not None:
            with open(self.creds_path, "w") as f:
                json.dump(self._creds, f)
            os.chmod(self.creds_path, 0o600)

    def _access_token(self) -> str:
        c = self._load()
        # 过期(留 60s 余量)→ 用 refresh_token 续
        if int(c.get("expiry_epoch", 0)) <= int(time.time()):
            body = urllib.parse.urlencode({
                "grant_type": "refresh_token",
                "refresh_token": c["refresh_token"],
                "client_id": c["client_id"],
                "client_secret": c["client_secret"],
            }).encode()
            req = urllib.request.Request(_TOKEN_URL, data=body,
                                         headers={"Content-Type": "application/x-www-form-urlencoded"})
            out = json.load(_opener().open(req, timeout=60))
            c["access_token"] = out["access_token"]
            c["expiry_epoch"] = int(time.time()) + int(out.get("expires_in", 3600)) - 60
            self._save()
        return c["access_token"]

    def _project(self) -> str:
        c = self._load()
        if c.get("project"):
            return c["project"]
        # loadCodeAssist 拿一次 project 并缓存
        res = self._post("loadCodeAssist", {
            "metadata": {"ideType": "IDE_UNSPECIFIED", "platform": "PLATFORM_UNSPECIFIED", "pluginType": "GEMINI"}
        })
        proj = res.get("cloudaicompanionProject") or ""
        c["project"] = proj
        self._save()
        return proj

    def _post(self, method: str, payload: dict) -> dict:
        req = urllib.request.Request(
            f"https://{_CODE_ASSIST_HOST}/v1internal:{method}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self._access_token()}", "Content-Type": "application/json"},
            method="POST",
        )
        with _opener().open(req, timeout=self.timeout_seconds) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @staticmethod
    def _to_contents(messages: list[dict]) -> tuple[list[dict], dict | None]:
        """OpenAI messages → Gemini contents + systemInstruction。"""
        contents: list[dict] = []
        sys_parts: list[dict] = []
        for m in messages:
            role = m.get("role")
            text = str(m.get("content", "") or "")
            if role == "system":
                sys_parts.append({"text": text})
            else:
                contents.append({"role": "model" if role == "assistant" else "user", "parts": [{"text": text}]})
        sys_instr = {"parts": sys_parts} if sys_parts else None
        return contents, sys_instr

    def chat(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.3,
        response_format: dict | None = None,
        max_retries: int = 3,
    ) -> str:
        contents, sys_instr = self._to_contents(messages)
        gen_cfg: dict = {"temperature": temperature}
        if response_format is not None:
            gen_cfg["responseMimeType"] = "application/json"
        request_body: dict = {"contents": contents, "generationConfig": gen_cfg}
        if sys_instr is not None:
            request_body["systemInstruction"] = sys_instr
        payload = {"model": self.model, "project": self._project(), "request": request_body}

        # 429 是临时限流(Gemini 标准档 RPM 紧),独立于 max_retries 多扛几次 —— 否则连
        # build_judge_client_resolved 的探活(max_retries=0)都会被一次瞬时 429 打回 self-judge。
        rate_limit_retries = 6  # 5/10/20/40/60/60s
        last_exc: Exception | None = None
        rl_attempt = 0
        attempt = 0
        while True:
            try:
                body = self._post("generateContent", payload)
                resp = body.get("response", body)
                parts = resp["candidates"][0]["content"]["parts"]
                return "".join(p.get("text", "") for p in parts)
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    if rl_attempt >= rate_limit_retries:
                        raise
                    time.sleep(min(5 * (2 ** rl_attempt), 60))
                    rl_attempt += 1
                    continue
                if exc.code < 500:  # 其他 4xx 直接抛
                    raise
                last_exc = exc
                if attempt >= max_retries:
                    raise
                time.sleep(2 ** (attempt + 1)); attempt += 1
            except (urllib.error.URLError, TimeoutError, KeyError, IndexError) as exc:
                last_exc = exc
                if attempt >= max_retries:
                    raise
                time.sleep(2 ** (attempt + 1)); attempt += 1


def build_gemini_judge() -> GeminiCodeAssistClient:
    return GeminiCodeAssistClient()
