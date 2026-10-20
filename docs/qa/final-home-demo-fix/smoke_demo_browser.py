"""Browser journey against Vite 4177 and real FastAPI 8001; no API interception."""

import base64
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "recovery-v2"))
from smoke_local_catalog_journey import Browser  # noqa: E402

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "evidence"
EVIDENCE.mkdir(exist_ok=True)


def snapshot(browser, name):
    data = browser.call("Page.captureScreenshot", {"format": "png"})["data"]
    (EVIDENCE / name).write_bytes(base64.b64decode(data))


def run_case(browser, kind, index, width):
    label = f"{kind}-{width}"
    browser.call("Page.navigate", {"url": "http://127.0.0.1:4177/"})
    browser.until("Boolean(document.querySelector('.simple-demo-grid'))", "home")
    browser.overflow(f"{label} home")
    browser.js(f"document.querySelectorAll('.simple-demo-grid button')[{index}].click()")
    browser.until("Boolean(document.querySelector('.demo-role-workspace .wr-primary'))", "demo preview", 30)
    if browser.js("document.querySelector('.demo-role-workspace input, .demo-role-workspace select') !== null"):
        raise AssertionError("locked demo exposes editable inputs")
    browser.overflow(f"{label} work")
    snapshot(browser, f"{label}-work.png")
    browser.js("document.querySelector('.demo-role-workspace .wr-primary').click()")
    browser.until("location.hash === '#robots' && Boolean(document.querySelector('.journey-actions .primary-action'))", "robots", 30)
    browser.js("document.querySelector('.journey-actions .primary-action').click()")
    browser.until("Boolean(document.querySelector('.scene-sim-controls button[type=submit]'))", "simulation", 30)
    browser.js("document.querySelector('.scene-sim-controls button[type=submit]').click()")
    browser.until("Boolean(document.querySelector('.scene-playback-controls [aria-label*=\"8×\"]'))", "live route", 30)
    browser.overflow(f"{label} simulation")
    browser.until("Boolean(document.querySelector('[data-robot-pose]'))", "robot pose", 30)
    pose0 = browser.js("document.querySelector('[data-robot-pose]').getAttribute('data-robot-pose')")
    browser.js("document.querySelector('.scene-playback-rates button:last-child').click()")
    time.sleep(1.5)
    pose1 = browser.js("document.querySelector('[data-robot-pose]').getAttribute('data-robot-pose')")
    if pose0 == pose1:
        raise AssertionError(f"{label}: robot did not move")
    browser.js("document.querySelector('.scene-playback-controls > button').click()")
    paused = browser.js("document.querySelector('[data-robot-pose]').getAttribute('data-robot-pose')")
    time.sleep(0.7)
    if browser.js("document.querySelector('[data-robot-pose]').getAttribute('data-robot-pose')") != paused:
        raise AssertionError(f"{label}: pause did not freeze robot")
    browser.js("document.querySelectorAll('.scene-preview-mobile-switch button')[1].click()")
    if browser.js("document.querySelector('.scene-preview-grid').dataset.mobileView") != "2d":
        raise AssertionError(f"{label}: 2D switch failed")
    browser.js("document.querySelectorAll('.scene-preview-mobile-switch button')[0].click()")
    if browser.js("document.querySelector('.scene-preview-grid').dataset.mobileView") != "3d":
        raise AssertionError(f"{label}: 3D switch failed")
    snapshot(browser, f"{label}-simulation.png")
    browser.js("document.querySelector('.journey-actions .primary-action').click()")
    browser.until("location.hash === '#money'", "money", 30)
    browser.overflow(f"{label} money")
    if browser.js("document.querySelector('.what-if-panel') !== null"):
        raise AssertionError(f"{label}: locked demo exposes What-if editor")
    browser.js("document.querySelector('.journey-actions .primary-action').click()")
    browser.until("location.hash === '#results'", "results", 30)
    snapshot(browser, f"{label}-result.png")
    browser.js("document.querySelector('.journey-actions button').click()")
    browser.until("Boolean(document.querySelector('.journey-actions button'))", "PDF action", 10)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and not any(
        row["url"].endswith("report.pdf") and row["status"] == 200 for row in browser.network
    ):
        browser.js("document.readyState")
        time.sleep(0.2)
    if not any(row["url"].endswith("report.pdf") and row["status"] == 200 for row in browser.network):
        raise AssertionError(f"{label}: PDF HTTP 200 not observed: {browser.network[-5:]}")
    overflow = browser.js("({width: innerWidth, scroll: document.documentElement.scrollWidth})")
    if overflow["scroll"] > overflow["width"] + 2:
        raise AssertionError(f"{label}: horizontal overflow {overflow}")
    return {"kind": kind, "width": width, "pose_before": pose0, "pose_after": pose1,
            "glb_status": browser.js("document.querySelector('[data-glb-status]')?.dataset.glbStatus"),
            "pdf_http": 200, "network": browser.network[-8:]}


if __name__ == "__main__":
    browser = Browser()
    browser.call("Page.bringToFront")
    results = []
    for width in (1440, 768, 390, 360):
        browser.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900,
                     "deviceScaleFactor": 1, "mobile": width <= 768})
        for index, kind in enumerate(("retail", "airport", "clinic")):
            results.append(run_case(browser, kind, index, width))
            print(f"PASS {kind} {width}", flush=True)
    (ROOT / "demo-browser-evidence.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
