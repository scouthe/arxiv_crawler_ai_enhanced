import time
import json
import re
from pathlib import Path
from typing import Any

import requests


class WechatAPIError(RuntimeError):
    def __init__(self, action: str, data: dict[str, Any]):
        self.action = action
        self.data = data
        try:
            self.errcode = int(data.get("errcode"))
        except Exception:
            self.errcode = None
        self.errmsg = str(data.get("errmsg", ""))
        super().__init__(f"{action} failed: {data}")

    @property
    def is_ip_whitelist_error(self) -> bool:
        msg = self.errmsg.lower()
        return self.errcode == 40164 or ("invalid ip" in msg and "whitelist" in msg)

    @property
    def hinted_ip(self) -> str | None:
        m = re.search(r"invalid ip\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", self.errmsg, flags=re.I)
        if m:
            return m.group(1)
        return None


def get_public_ip(timeout: int = 5) -> str | None:
    providers: list[tuple[str, str]] = [
        ("https://api64.ipify.org?format=json", "json"),
        ("https://ifconfig.me/ip", "text"),
        ("https://checkip.amazonaws.com", "text"),
    ]
    for url, mode in providers:
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            if mode == "json":
                ip = str(resp.json().get("ip", "")).strip()
            else:
                ip = resp.text.strip()
            if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+", ip):
                return ip
        except Exception:
            continue
    return None


class WechatClient:
    def __init__(self, app_id: str, app_secret: str, timeout: int = 30):
        self.app_id = app_id
        self.app_secret = app_secret
        self.timeout = timeout
        self._token: str | None = None
        self._token_expire_at: float = 0

    def _fetch_access_token(self) -> str:
        url = "https://api.weixin.qq.com/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": self.app_id,
            "secret": self.app_secret,
        }
        resp = requests.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        if "access_token" not in data:
            raise WechatAPIError("get access_token", data)
        token = data["access_token"]
        expires_in = int(data.get("expires_in", 7200))
        self._token = token
        self._token_expire_at = time.time() + max(60, expires_in - 120)
        return token

    def get_access_token(self, force_refresh: bool = False) -> str:
        if not force_refresh and self._token and time.time() < self._token_expire_at:
            return self._token
        return self._fetch_access_token()

    def upload_image_material(self, image_path: Path) -> dict:
        token = self.get_access_token()
        url = "https://api.weixin.qq.com/cgi-bin/material/add_material"
        params = {"access_token": token, "type": "image"}
        with open(image_path, "rb") as f:
            files = {"media": (image_path.name, f)}
            resp = requests.post(url, params=params, files=files, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode"):
            raise WechatAPIError("upload image", data)
        return data

    def add_draft(self, articles: list[dict]) -> dict:
        token = self.get_access_token()
        url = "https://api.weixin.qq.com/cgi-bin/draft/add"
        params = {"access_token": token}
        payload = {"articles": articles}
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        resp = requests.post(
            url,
            params=params,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode"):
            raise WechatAPIError("add draft", data)
        return data
