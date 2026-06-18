import os
from pathlib import Path


def sanitize_profile_name(name: str) -> str:
    value = "".join(ch for ch in str(name or "") if ch.isdigit())
    return value or str(name or "default")


def resolve_profile_dir(profile_dir: str, phone: str | None = None) -> str:
    base = Path(profile_dir)
    if not phone:
        return str(base)

    safe_phone = sanitize_profile_name(phone)
    if base.name == safe_phone:
        return str(base)
    return str(base / safe_phone)


def cleanup_stale_singleton(profile_dir: str) -> bool:
    removed = False
    for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        path = Path(profile_dir) / name
        try:
            if path.exists() or path.is_symlink():
                path.unlink()
                removed = True
        except FileNotFoundError:
            continue
    return removed


def launch_persistent_context_with_retry(playwright, **options):
    launcher = playwright.chromium.launch_persistent_context
    user_data_dir = str(options.get("user_data_dir") or "")

    try:
        return launcher(**options)
    except Exception as exc:
        message = str(exc)
        if "ProcessSingleton" not in message or not user_data_dir:
            raise
        if not cleanup_stale_singleton(user_data_dir):
            raise
        return launcher(**options)


def chromium_context_options(**options):
    chrome_bin = os.getenv("CHROME_BIN", "").strip() or os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE", "").strip()
    if chrome_bin:
        options["executable_path"] = chrome_bin
    return options
