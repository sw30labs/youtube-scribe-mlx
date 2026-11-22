import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import ytdlp_opts as yo


class ParseCookiesEnvTests(unittest.TestCase):
    def test_blank_and_off_disable(self):
        self.assertIsNone(yo.parse_cookies_from_browser_env(""))
        self.assertIsNone(yo.parse_cookies_from_browser_env(" none "))
        self.assertIsNone(yo.parse_cookies_from_browser_env("OFF"))
        self.assertIsNone(yo.parse_cookies_from_browser_env("0"))

    def test_browser_and_profile(self):
        self.assertEqual(yo.parse_cookies_from_browser_env("chrome"), ("chrome",))
        self.assertEqual(yo.parse_cookies_from_browser_env("Chrome:Default"), ("chrome", "Default"))
        self.assertEqual(
            yo.parse_cookies_from_browser_env("chrome:/tmp/profile"),
            ("chrome", "/tmp/profile"),
        )


class CookieStoreSearchableTests(unittest.TestCase):
    def test_chromium_dir_listable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertTrue(yo.browser_cookie_store_searchable("chrome", temp_dir))

    def test_chromium_dir_permission_denied(self):
        with mock.patch.object(yo.os, "listdir", side_effect=PermissionError("Operation not permitted")):
            self.assertFalse(
                yo.browser_cookie_store_searchable(
                    "chrome",
                    "/Users/spider/Library/Application Support/Google/Chrome",
                )
            )

    def test_missing_dir_is_not_searchable(self):
        self.assertFalse(
            yo.browser_cookie_store_searchable("chrome", "/tmp/does-not-exist-ytdlp-opts")
        )

    def test_safari_readable_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cookies = Path(temp_dir) / "Cookies.binarycookies"
            cookies.write_bytes(b"cook")
            self.assertTrue(yo.browser_cookie_store_searchable("safari", str(cookies)))

    def test_unknown_browser_without_path_lets_ytdlp_try(self):
        self.assertTrue(yo.browser_cookie_store_searchable("firefox"))


class BaseOptsTests(unittest.TestCase):
    def setUp(self):
        yo._cookies_warning_emitted = False

    def test_omits_cookies_when_store_blocked(self):
        environ = {}
        with mock.patch.object(yo, "browser_cookie_store_searchable", return_value=False):
            opts = yo.ytdlp_base_opts(environ=environ, format="bestaudio/best")
        self.assertNotIn("cookiesfrombrowser", opts)
        self.assertEqual(opts["format"], "bestaudio/best")
        self.assertEqual(opts["js_runtimes"], {"deno": {}, "node": {}})

    def test_includes_chrome_when_searchable(self):
        environ = {}
        with mock.patch.object(yo, "browser_cookie_store_searchable", return_value=True):
            opts = yo.ytdlp_base_opts(environ=environ)
        self.assertEqual(opts["cookiesfrombrowser"], ("chrome",))

    def test_env_none_disables_even_if_searchable(self):
        environ = {"YTDLP_COOKIES_FROM_BROWSER": "none"}
        with mock.patch.object(yo, "browser_cookie_store_searchable", return_value=True):
            opts = yo.ytdlp_base_opts(environ=environ)
        self.assertNotIn("cookiesfrombrowser", opts)

    def test_cookiefile_env(self):
        environ = {
            "YTDLP_COOKIEFILE": "~/cookies.txt",
            "YTDLP_COOKIES_FROM_BROWSER": "none",
        }
        opts = yo.ytdlp_base_opts(environ=environ)
        self.assertEqual(opts["cookiefile"], os.path.expanduser("~/cookies.txt"))
        self.assertNotIn("cookiesfrombrowser", opts)

    def test_explicit_safari_when_searchable(self):
        environ = {"YTDLP_COOKIES_FROM_BROWSER": "safari"}
        with mock.patch.object(yo, "browser_cookie_store_searchable", return_value=True) as searchable:
            opts = yo.ytdlp_base_opts(environ=environ)
        searchable.assert_called_with("safari", None)
        self.assertEqual(opts["cookiesfrombrowser"], ("safari",))


class FakeYDL:
    def __init__(self, opts):
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def extract_info(self, url, download=False):
        if self.opts.get("cookiesfrombrowser"):
            raise RuntimeError(
                'ERROR: could not find chrome cookies database in '
                '"/Users/spider/Library/Application Support/Google/Chrome"'
            )
        return {"id": "eHd4rdZDIYY", "title": "ok", "url": url, "download": download}


class ExtractInfoRetryTests(unittest.TestCase):
    def test_retries_without_cookies_on_missing_db(self):
        opts = {"cookiesfrombrowser": ("chrome",), "quiet": True}
        info, ydl = yo._extract_info(FakeYDL, opts, "https://youtu.be/eHd4rdZDIYY", download=False)
        self.assertEqual(info["id"], "eHd4rdZDIYY")
        self.assertNotIn("cookiesfrombrowser", ydl.opts)

    def test_non_cookie_errors_are_not_swallowed(self):
        class BoomYDL(FakeYDL):
            def extract_info(self, url, download=False):
                raise RuntimeError("HTTP Error 429: Too Many Requests")

        with self.assertRaisesRegex(RuntimeError, "429"):
            yo._extract_info(
                BoomYDL,
                {"cookiesfrombrowser": ("chrome",)},
                "https://youtu.be/eHd4rdZDIYY",
                download=False,
            )

    def test_is_cookie_error(self):
        self.assertTrue(
            yo.is_cookie_error(
                RuntimeError('could not find chrome cookies database in "/x"')
            )
        )
        self.assertFalse(yo.is_cookie_error(RuntimeError("HTTP Error 429")))


if __name__ == "__main__":
    unittest.main()
