import os


def chromium_context_options(**options):
    chrome_bin = os.getenv("CHROME_BIN", "").strip() or os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE", "").strip()
    if chrome_bin:
        options["executable_path"] = chrome_bin
    return options
