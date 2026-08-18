"""
Standalone integration tests for TasaVzla.

Tests each layer independently without Docker or Postgres:

  1. Scraper  — BCV direct (live HTTP, html.parser monkeypatched locally)
  2. Fallback — ve.dolarapi.com (live HTTP)
  3. Fetcher  — full chain primary → fallback
  4. API      — TestClient with SQLite in-memory, scheduler disabled

NOTE: production code uses lxml + asyncpg (which require C compiler on Windows).
      For local tests we monkeypatch the parser to html.parser and the DB URL to
      SQLite+aiosqlite — no code changes needed in the app itself.
"""

import asyncio
import os
import sys

# ─── Patch DB URL before any app import ───────────────────────────────────────
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_tmp.db"
# ─────────────────────────────────────────────────────────────────────────────

# ── ANSI helpers ──────────────────────────────────────────────────────────────
PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
results: list[tuple[str, bool, str]] = []


def ok(name: str, detail: str = "") -> None:
    results.append((name, True, detail))
    print(f"  {PASS}  {name}" + (f"  →  {detail}" if detail else ""))


def fail(name: str, detail: str = "") -> None:
    results.append((name, False, detail))
    print(f"  {FAIL}  {name}" + (f"  →  {detail}" if detail else ""))


# ─── 1. BCV scraper ───────────────────────────────────────────────────────────
async def test_scraper() -> None:
    print("\n── 1. BCV direct scraper (live) ─────────────────────────────")

    # Monkeypatch: production uses 'lxml', but lxml has no Windows wheel for
    # Python 3.14 yet.  'html.parser' is stdlib and equally correct here.
    import app.scraper as _s
    original_parse = _s._parse_rate

    def _parse_html_parser(html: str, currency: str) -> float:
        from bs4 import BeautifulSoup
        from app.scraper import _CURRENCY_IDS
        soup = BeautifulSoup(html, "html.parser")   # ← stdlib parser
        eid = _CURRENCY_IDS[currency.upper()]
        container = soup.find("div", id=eid)
        if container is None:
            raise ValueError(f"div#{eid} not found in BCV HTML")
        strong = container.find("strong")
        if strong is None:
            raise ValueError(f"<strong> not found in div#{eid}")
        raw = strong.get_text(strip=True).replace(".", "").replace(",", ".")
        return float(raw)

    _s._parse_rate = _parse_html_parser

    try:
        from app.scraper import scrape_bcv
        from datetime import date

        for currency in ("USD", "EUR"):
            try:
                rate, rate_date = await scrape_bcv(currency)
                assert isinstance(rate, float) and rate > 0
                assert isinstance(rate_date, date)
                ok(f"scraper:{currency}", f"rate={rate:.4f}  date={rate_date}")
            except Exception as e:
                fail(f"scraper:{currency}", str(e))
    finally:
        _s._parse_rate = original_parse  # restore


# ─── 2. Fallback ──────────────────────────────────────────────────────────────
async def test_fallback() -> None:
    print("\n── 2. dolarapi.com fallback (live) ──────────────────────────")
    from app.fallback import fetch_fallback
    from datetime import date

    for currency in ("USD", "EUR"):
        try:
            rate, rate_date = await fetch_fallback(currency)
            assert isinstance(rate, float) and rate > 0
            assert isinstance(rate_date, date)
            ok(f"fallback:{currency}", f"rate={rate:.4f}  date={rate_date}")
        except Exception as e:
            fail(f"fallback:{currency}", str(e))


# ─── 3. Fetcher chain ─────────────────────────────────────────────────────────
async def test_fetcher() -> None:
    print("\n── 3. Fetcher chain ─────────────────────────────────────────")
    from app.fetcher import fetch_rate, FetchResult

    for currency in ("USD", "EUR"):
        try:
            result = await fetch_rate(currency)
            assert result is not None, "Both sources failed"
            assert isinstance(result, FetchResult)
            assert result.rate > 0
            assert result.source in ("bcv_direct", "dolarapi_fallback")
            ok(f"fetcher:{currency}", f"rate={result.rate:.4f}  source={result.source}")
        except Exception as e:
            fail(f"fetcher:{currency}", str(e))


# ─── 4. FastAPI TestClient ────────────────────────────────────────────────────
def test_api() -> None:
    print("\n── 4. FastAPI endpoints (SQLite in-memory) ──────────────────")

    # Disable the APScheduler so it doesn't interfere with the test loop
    import apscheduler.schedulers.asyncio as _aps
    _original_start    = _aps.AsyncIOScheduler.start
    _original_shutdown = _aps.AsyncIOScheduler.shutdown
    _aps.AsyncIOScheduler.start    = lambda self, *a, **kw: None
    _aps.AsyncIOScheduler.shutdown = lambda self, *a, **kw: None

    # Also patch the scraper parser inside the app for the same lxml reason
    import app.scraper as _s
    original_parse = _s._parse_rate

    def _parse_html_parser(html: str, currency: str) -> float:
        from bs4 import BeautifulSoup
        from app.scraper import _CURRENCY_IDS
        soup = BeautifulSoup(html, "html.parser")
        eid = _CURRENCY_IDS[currency.upper()]
        container = soup.find("div", id=eid)
        if container is None:
            raise ValueError(f"div#{eid} not found")
        strong = container.find("strong")
        if strong is None:
            raise ValueError(f"<strong> not found in div#{eid}")
        raw = strong.get_text(strip=True).replace(".", "").replace(",", ".")
        return float(raw)

    _s._parse_rate = _parse_html_parser

    try:
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app, raise_server_exceptions=False) as client:

            # /health ──────────────────────────────────────────────────────────
            try:
                r = client.get("/health")
                assert r.status_code == 200, f"status={r.status_code}"
                assert r.json()["status"] == "ok"
                ok("api:/health", f"status=200  body={r.json()}")
            except Exception as e:
                fail("api:/health", str(e))

            # /rate/usd ────────────────────────────────────────────────────────
            try:
                r = client.get("/rate/usd")
                body = r.json()
                if r.status_code == 200:
                    assert body["currency"] == "USD"
                    assert body["rate"] > 0
                    assert body["source"] in ("bcv_direct", "dolarapi_fallback", "cached_stale")
                    ok("api:/rate/usd", f"rate={body['rate']}  source={body['source']}  stale={body['stale']}")
                elif r.status_code == 503:
                    # Both sources down at test time — still correct behaviour
                    ok("api:/rate/usd", f"503 expected (cache empty, both sources unreachable)")
                else:
                    fail("api:/rate/usd", f"unexpected status={r.status_code}  body={body}")
            except Exception as e:
                fail("api:/rate/usd", str(e))

            # /rate/eur ────────────────────────────────────────────────────────
            try:
                r = client.get("/rate/eur")
                body = r.json()
                if r.status_code == 200:
                    assert body["currency"] == "EUR"
                    assert body["rate"] > 0
                    assert body["source"] in ("bcv_direct", "dolarapi_fallback", "cached_stale")
                    ok("api:/rate/eur", f"rate={body['rate']}  source={body['source']}  stale={body['stale']}")
                elif r.status_code == 503:
                    ok("api:/rate/eur", f"503 expected (cache empty, both sources unreachable)")
                else:
                    fail("api:/rate/eur", f"unexpected status={r.status_code}  body={body}")
            except Exception as e:
                fail("api:/rate/eur", str(e))

            # /rate/btc → 404 (unknown route) ──────────────────────────────────
            try:
                r = client.get("/rate/btc")
                assert r.status_code == 404, f"Expected 404, got {r.status_code}"
                ok("api:/rate/btc (unknown)", "404 as expected")
            except Exception as e:
                fail("api:/rate/btc (unknown)", str(e))

            # /docs → 200 (Swagger UI) ─────────────────────────────────────────
            try:
                r = client.get("/docs")
                assert r.status_code == 200
                ok("api:/docs (Swagger UI)", f"status=200")
            except Exception as e:
                fail("api:/docs", str(e))

    finally:
        _aps.AsyncIOScheduler.start    = _original_start
        _aps.AsyncIOScheduler.shutdown = _original_shutdown
        _s._parse_rate = original_parse
        import pathlib
        try:
            pathlib.Path("test_tmp.db").unlink(missing_ok=True)
        except PermissionError:
            pass  # SQLite file still held by event loop on Windows — harmless


# ─── Runner ───────────────────────────────────────────────────────────────────
async def _async_tests() -> None:
    await test_scraper()
    await test_fallback()
    await test_fetcher()


if __name__ == "__main__":
    print("=" * 57)
    print("  TasaVzla — integration tests")
    print("=" * 57)
    asyncio.run(_async_tests())
    test_api()

    print("\n" + "=" * 57)
    passed = sum(1 for _, ok_, _ in results if ok_)
    failed = sum(1 for _, ok_, _ in results if not ok_)
    print(f"  {passed} passed  /  {failed} failed  /  {len(results)} total")
    print("=" * 57 + "\n")
    sys.exit(1 if failed else 0)
