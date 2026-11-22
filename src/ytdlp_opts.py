#!/usr/bin/env python3
"""yt-dlp option helpers.

Chrome cookies are optional. On macOS, Terminal often cannot *list*
``~/Library/Application Support/Google/Chrome`` (TCC), so yt-dlp's directory
walk reports "could not find chrome cookies database" even when
``Default/Cookies`` exists. That used to abort the whole download.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional, Tuple


CookiesSpec = Tuple[str, ...]

_CHROMIUM_BROWSERS = ("brave", "chrome", "chromium", "edge", "opera", "vivaldi", "whale")
_COOKIE_ERROR_MARKERS = (
    "cookies database",
    "failed to load cookies",
    "could not copy chrome cookie",
    "cookie load",
)
_cookies_warning_emitted = False


def _is_path(value: str) -> bool:
    return any(sep in value for sep in (os.path.sep, os.path.altsep) if sep)


def parse_cookies_from_browser_env(value: Optional[str]) -> Optional[CookiesSpec]:
    """Parse ``YTDLP_COOKIES_FROM_BROWSER``.

    ``None`` (unset) means the caller should use the default browser list.
    ``none`` / ``off`` / ``0`` disables browser cookies.
    Otherwise ``browser`` or ``browser:profile-or-path``.
    """
    if value is None:
        return None
    text = value.strip()
    if not text or text.lower() in {"none", "off", "0", "false", "no"}:
        return None
    if ":" in text:
        browser, rest = text.split(":", 1)
        browser = browser.strip().lower()
        rest = rest.strip()
        if not browser:
            return None
        return (browser, rest) if rest else (browser,)
    return (text.lower(),)


def chromium_browser_dir(browser: str) -> Optional[str]:
    """Return yt-dlp's default profile root for a Chromium-based browser."""
    browser = browser.lower()
    if sys.platform == "darwin":
        appdata = os.path.expanduser("~/Library/Application Support")
        mapping = {
            "brave": os.path.join(appdata, "BraveSoftware/Brave-Browser"),
            "chrome": os.path.join(appdata, "Google/Chrome"),
            "chromium": os.path.join(appdata, "Chromium"),
            "edge": os.path.join(appdata, "Microsoft Edge"),
            "opera": os.path.join(appdata, "com.operasoftware.Opera"),
            "vivaldi": os.path.join(appdata, "Vivaldi"),
            "whale": os.path.join(appdata, "Naver/Whale"),
        }
    elif sys.platform in ("win32", "cygwin"):
        appdata_local = os.environ.get("LOCALAPPDATA", "")
        appdata_roaming = os.environ.get("APPDATA", "")
        mapping = {
            "brave": os.path.join(appdata_local, r"BraveSoftware\Brave-Browser\User Data"),
            "chrome": os.path.join(appdata_local, r"Google\Chrome\User Data"),
            "chromium": os.path.join(appdata_local, r"Chromium\User Data"),
            "edge": os.path.join(appdata_local, r"Microsoft\Edge\User Data"),
            "opera": os.path.join(appdata_roaming, r"Opera Software\Opera Stable"),
            "vivaldi": os.path.join(appdata_local, r"Vivaldi\User Data"),
            "whale": os.path.join(appdata_local, r"Naver\Naver Whale\User Data"),
        }
    else:
        config = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        mapping = {
            "brave": os.path.join(config, "BraveSoftware/Brave-Browser"),
            "chrome": os.path.join(config, "google-chrome"),
            "chromium": os.path.join(config, "chromium"),
            "edge": os.path.join(config, "microsoft-edge"),
            "opera": os.path.join(config, "opera"),
            "vivaldi": os.path.join(config, "vivaldi"),
            "whale": os.path.join(config, "naver-whale"),
        }
    return mapping.get(browser)


def cookie_search_root(browser: str, profile: Optional[str] = None) -> Optional[str]:
    """Directory yt-dlp would walk, or Safari's cookies file path."""
    browser = browser.lower()
    if profile and _is_path(profile):
        return os.path.expanduser(profile)
    if browser == "safari":
        if profile:
            return os.path.expanduser(profile)
        primary = os.path.expanduser("~/Library/Cookies/Cookies.binarycookies")
        if os.path.isfile(primary):
            return primary
        return os.path.expanduser(
            "~/Library/Containers/com.apple.Safari/Data/Library/Cookies/Cookies.binarycookies"
        )
    root = chromium_browser_dir(browser)
    if root is None:
        return None
    if profile:
        return os.path.join(root, profile)
    return root


def _dir_is_searchable(path: str) -> bool:
    try:
        os.listdir(path)
        return True
    except OSError:
        return False


def _file_is_readable(path: str) -> bool:
    """True only if the file can actually be opened (unix mode can lie under TCC)."""
    try:
        with open(path, "rb") as handle:
            handle.read(1)
        return True
    except OSError:
        return False


def browser_cookie_store_searchable(browser: str, profile: Optional[str] = None) -> bool:
    """True when yt-dlp is likely to find this browser's cookie DB.

    Chromium extractors walk the profile root with ``os.walk``. If that
    listing is blocked (typical macOS TCC), they raise FileNotFoundError.
    Unknown browsers return True so an explicit env override still runs.
    """
    browser = browser.lower()
    root = cookie_search_root(browser, profile)
    if root is None:
        return True
    if browser == "safari":
        return _file_is_readable(root)
    if browser in _CHROMIUM_BROWSERS:
        return _dir_is_searchable(root)
    return _dir_is_searchable(root)


def is_cookie_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in _COOKIE_ERROR_MARKERS)


def _warn_cookies_unavailable(browser: str) -> None:
    global _cookies_warning_emitted
    if _cookies_warning_emitted:
        return
    _cookies_warning_emitted = True
    print(
        f"Warning: cannot read {browser} cookies "
        "(macOS Full Disk Access is often required to list the browser profile). "
        "Downloading without login cookies."
    )


def resolved_cookiesfrombrowser(environ: Optional[Dict[str, str]] = None) -> Optional[CookiesSpec]:
    env = os.environ if environ is None else environ
    raw = env.get("YTDLP_COOKIES_FROM_BROWSER")
    if raw is not None:
        spec = parse_cookies_from_browser_env(raw)
        if spec is None:
            return None
        profile = spec[1] if len(spec) > 1 else None
        if browser_cookie_store_searchable(spec[0], profile):
            return spec
        _warn_cookies_unavailable(spec[0])
        return None

    for spec in (("chrome",), ("safari",)):
        profile = spec[1] if len(spec) > 1 else None
        if browser_cookie_store_searchable(spec[0], profile):
            return spec
    _warn_cookies_unavailable("chrome")
    return None


def ytdlp_base_opts(environ: Optional[Dict[str, str]] = None, **extra: Any) -> Dict[str, Any]:
    """Shared yt-dlp options, with cookies only when the store is readable."""
    env = os.environ if environ is None else environ
    opts: Dict[str, Any] = {
        "remote_components": ["ejs:github"],
        # yt-dlp defaults to deno only; enable node so the n-challenge
        # can be solved on machines without deno installed
        "js_runtimes": {"deno": {}, "node": {}},
    }
    cookiefile = env.get("YTDLP_COOKIEFILE")
    if cookiefile:
        opts["cookiefile"] = os.path.expanduser(cookiefile)
    spec = resolved_cookiesfrombrowser(env)
    if spec:
        opts["cookiesfrombrowser"] = spec
    opts.update(extra)
    return opts


def extract_info(opts: Dict[str, Any], url: str, download: bool = False):
    """``YoutubeDL.extract_info``, retrying once if browser cookies fail."""
    import yt_dlp

    return _extract_info(yt_dlp.YoutubeDL, opts, url, download)


def _extract_info(ydl_cls, opts: Dict[str, Any], url: str, download: bool):
    attempt = dict(opts)
    try:
        with ydl_cls(attempt) as ydl:
            return ydl.extract_info(url, download=download), ydl
    except Exception as exc:
        if "cookiesfrombrowser" not in attempt or not is_cookie_error(exc):
            raise
        print(f"Warning: browser cookies failed ({exc}). Retrying without cookies.")
        attempt.pop("cookiesfrombrowser", None)
        with ydl_cls(attempt) as ydl:
            return ydl.extract_info(url, download=download), ydl
