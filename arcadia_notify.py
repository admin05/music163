import os
import urllib.parse

import requests


DEFAULT_BARK_SERVER = "https://api.day.app"


def _truncate_text(text: str, limit: int = 3200) -> str:
    text = str(text or "")
    if len(text) <= limit:
        return text
    return f"{text[: limit - 120]}\n\n...(内容过长已截断)..."


def _bark_endpoint(bark_value: str) -> str:
    bark_value = bark_value.strip()
    if bark_value.startswith(("http://", "https://")):
        return bark_value.rstrip("/")

    server = os.getenv("BARK_SERVER", DEFAULT_BARK_SERVER).strip().rstrip("/")
    return f"{server}/{urllib.parse.quote(bark_value, safe='')}"


def send_bark(title: str, body: str, *, level: str = "active", timeout: int = 12) -> bool:
    """Send a Bark notification using BARK from the environment.

    BARK can be either a device key or a full Bark endpoint URL. Missing BARK is
    treated as a no-op so the Arcadia task can still finish normally.
    """
    bark_value = os.getenv("BARK", "").strip()
    if not bark_value:
        print("[Bark] BARK 环境变量未配置，跳过推送。")
        return False

    endpoint = _bark_endpoint(bark_value)
    payload = {
        "title": title,
        "body": _truncate_text(body),
        "group": os.getenv("BARK_GROUP", "网易音乐人任务"),
        "level": os.getenv("BARK_LEVEL", level),
    }

    icon = os.getenv("BARK_ICON", "").strip()
    if icon:
        payload["icon"] = icon

    try:
        response = requests.post(endpoint, json=payload, timeout=timeout)
        if response.status_code != 200:
            print(f"[Bark] 推送失败：HTTP {response.status_code}")
            return False
        data = response.json() if response.content else {}
        if isinstance(data, dict) and data.get("code") not in (None, 200):
            print(f"[Bark] 推送失败：{data}")
            return False
        print("[Bark] 推送成功。")
        return True
    except Exception as exc:
        print(f"[Bark] 推送异常：{exc}")
        return False
