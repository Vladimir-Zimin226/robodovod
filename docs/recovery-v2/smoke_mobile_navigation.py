"""Check the actual mobile menu and assistant dialog in Edge, independent of API mocks."""

import json

from smoke_local_catalog_journey import Browser, OUT, URL


def main():
    browser = Browser()
    results = []
    try:
        for width in (360, 390, 768):
            browser.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 800,
                         "deviceScaleFactor": 1, "mobile": True})
            browser.call("Page.navigate", {"url": URL})
            browser.until("Boolean(document.querySelector('.mobile-menu-button'))", "home")
            browser.overflow(f"{width} home")
            browser.js("document.querySelector('.mobile-menu-button').click()")
            browser.until("Boolean(document.querySelector('.app-sidebar.is-open'))", "menu")
            browser.capture(f"mobile-{width}-menu.png")
            browser.js("document.querySelector('.sidebar-scrim').click()")
            browser.until("!document.querySelector('.app-sidebar.is-open')", "closed menu")
            browser.js("document.querySelector('.rd-help-launcher').click()")
            browser.until("Boolean(document.querySelector('#rd-help-dialog'))", "assistant")
            bounds = browser.js("(()=>{const r=document.querySelector('#rd-help-dialog').getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}})()")
            if bounds["left"] < -1 or bounds["right"] > width + 1 or bounds["top"] < -1 or bounds["bottom"] > 801:
                raise RuntimeError(f"{width}: assistant dialog escapes viewport: {bounds}")
            browser.capture(f"mobile-{width}-chat.png")
            browser.js("document.querySelector('[aria-label=\"Закрыть чат\"]').click()")
            browser.until("!document.querySelector('#rd-help-dialog')", "closed assistant")
            results.append({"width": width, "menu": "PASS", "chat": "PASS", "dialog_bounds": bounds})
    finally:
        browser.call("Emulation.clearDeviceMetricsOverride")
        browser.ws.close()
    (OUT / "mobile-navigation.json").write_text(json.dumps({"cases": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PASS: {len(results)} mobile menu/chat widths", flush=True)


if __name__ == "__main__":
    main()
