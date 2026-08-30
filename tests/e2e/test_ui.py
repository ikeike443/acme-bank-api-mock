"""Browser-level end-to-end coverage for the local banking UI."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from urllib.request import urlopen

import pytest
from playwright.sync_api import Page, expect, sync_playwright


@pytest.fixture(scope="session")
def api_server() -> Iterator[str]:
    """Start a clean API process so the browser exercises real HTTP routes."""
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_url = "http://127.0.0.1:8765"
    try:
        for _ in range(50):
            try:
                with urlopen(f"{base_url}/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("API server did not start")
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def test_user_can_log_in_and_complete_a_transfer(api_server: str) -> None:
    headless = os.getenv("E2E_HEADFUL", "").lower() not in {"1", "true", "yes"}
    with sync_playwright() as playwright:
        launch_options = {
            "headless": headless,
            "slow_mo": 100 if not headless else 0,
        }
        local_chrome = Path.home() / ".agent-browser/browsers/chrome-152.0.7977.64/chrome"
        if local_chrome.exists():
            launch_options["executable_path"] = str(local_chrome)
        browser = playwright.chromium.launch(**launch_options)
        page: Page = browser.new_page()
        page.goto(api_server, wait_until="networkidle")

        expect(
            page.get_by_role(
                "heading",
                name=re.compile(r"安全な銀行体験を、\s*シンプルに。"),
            )
        ).to_be_visible()
        page.get_by_label("口座番号").fill("1")
        page.get_by_label("暗証番号").fill("1234")
        page.get_by_role("button", name="ログインする").click()

        try:
            expect(page.get_by_text("こんにちは、Alice Tanakaさん")).to_be_visible()
            expect(page.get_by_test_id("account-balance")).to_have_text("￥2,000,000")

            page.get_by_label("送金額").fill("10000")
            page.get_by_role("button", name="送金する").click()

            expect(page.get_by_role("status")).to_have_text("￥10,000の送金が完了しました。")
            expect(page.get_by_test_id("account-balance")).to_have_text("￥1,990,000")
        finally:
            browser.close()
