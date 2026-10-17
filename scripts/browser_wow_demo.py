"""Local visual smoke for the two public warehouse scenarios and plan editor.

Serve frontend/dist on 127.0.0.1:5194 first. This script does not submit API data.
"""

from __future__ import annotations

from pathlib import Path
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from local_browser import LocalBrowser  # noqa: E402


def main() -> None:
    output = ROOT / ".tmp/wow-browser"
    browser = LocalBrowser("http://127.0.0.1:5194/", output, software_gpu=True)
    try:
        browser.viewport(1366)
        browser.until("document.querySelector('.landing-preview') !== null")
        assert browser.js("document.querySelectorAll('.landing-amr').length") == 4
        browser.screenshot("01-landing-desktop.png")
        browser.js("[...document.querySelectorAll('.landing-preview-switch button')].find(b=>b.textContent.includes('2 400')).click()")
        assert browser.js("document.querySelector('.landing-preview-metrics').innerText.includes('22')")
        browser.js("[...document.querySelectorAll('.landing-actions button')].find(b=>b.textContent.includes('Смотреть два сценария')).click()")
        browser.until("document.querySelector('.guest-demo-choice') !== null")
        browser.screenshot("02-demo-choice.png")
        browser.until("document.querySelector('.robcraft-frame iframe') !== null")
        time.sleep(7)
        browser.js("document.querySelector('.guest-demo-simulation').scrollIntoView()")
        browser.screenshot("03-demo-3d.png")
        browser.js("[...document.querySelectorAll('.guest-demo-choice button')].find(b=>b.textContent.includes('2 400')).click()")
        browser.until("document.querySelector('.guest-demo-comparison').innerText.includes('22')")
        assert browser.js("document.querySelector('a[download=\"warehouse-pallet-peak-v1.pdf\"]') !== null")
        browser.js("[...document.querySelectorAll('.simulation-view-tabs button')].find(b=>b.textContent==='2D').click()")
        browser.until("document.querySelector('.facility-plan svg') !== null")
        browser.js("document.querySelector('.guest-demo-simulation').scrollIntoView()")
        browser.screenshot("04-demo-peak-2d.png")
        browser.viewport(390)
        browser.js("window.scrollTo(0,0)")
        browser.screenshot("05-demo-mobile.png")
        browser.js("[...document.querySelectorAll('.guest-demo-actions button')].find(b=>b.textContent.includes('Открыть ввод')).click()")
        browser.until("document.querySelector('.warehouse-layout-sketch') !== null")
        browser.js("[...document.querySelectorAll('.warehouse-layout-heading button')][0].click()")
        browser.until("document.querySelector('.warehouse-layout-map svg') !== null")
        browser.js("(()=>{const svg=document.querySelector('.warehouse-layout-map svg'); const r=svg.getBoundingClientRect(); svg.dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:r.left+r.width/2,clientY:r.top+r.height/2}));})()")
        browser.until("document.querySelector('.warehouse-layout-footer').innerText.includes('1 объектов')")
        browser.js("document.querySelector('.warehouse-layout-sketch').scrollIntoView()")
        browser.screenshot("06-layout-mobile.png")
        assert browser.js("document.documentElement.scrollWidth <= window.innerWidth + 1")
        browser.js("[...document.querySelectorAll('.warehouse-layout-dimensions button')].find(b=>b.textContent.includes('учебный план')).click()")
        browser.until("document.querySelector('.warehouse-layout-route').innerText.includes('Проходимый путь')")
        browser.js("document.querySelector('.warehouse-layout-route').scrollIntoView()")
        browser.screenshot("07-layout-route-mobile.png")
        browser.js("[...document.querySelectorAll('.warehouse-layout-views button')].find(b=>b.textContent.includes('Объёмный')).click()")
        browser.until("document.querySelector('.warehouse-layout-volume') !== null")
        browser.js("document.querySelector('.warehouse-layout-map').scrollIntoView()")
        browser.screenshot("08-layout-volume-mobile.png")
        browser.js("[...document.querySelectorAll('.warehouse-layout-views button')].find(b=>b.textContent.includes('сверху')).click()")
        browser.js("document.querySelector('.warehouse-layout-apply button').click()")
        browser.until("document.querySelector('.warehouse-layout-applied')?.innerText.includes('52')")
        browser.js("document.querySelector('.warehouse-layout-tools button[aria-pressed=\"true\"]').click()")
        browser.js("(()=>{const svg=document.querySelector('.warehouse-layout-map svg'); const r=svg.getBoundingClientRect(); svg.dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:r.left+r.width*.73,clientY:r.top+r.height*.77}));})()")
        browser.until("document.querySelector('.warehouse-layout-applied') === null")
        browser.js("document.querySelector('.warehouse-dxf-importer summary').click()")
        sample_dxf = "\n".join(["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "6", "0", "ENDSEC",
            "0", "SECTION", "2", "ENTITIES",
            "0", "LINE", "8", "WALL", "10", "0", "20", "0", "11", "60", "21", "0",
            "0", "LINE", "8", "WALL", "10", "30", "20", "0", "11", "30", "21", "36",
            "0", "ENDSEC", "0", "EOF"])
        browser.js("(()=>{const input=document.querySelector('.warehouse-dxf-importer input[type=file]'); const transfer=new DataTransfer(); transfer.items.add(new File([" + json.dumps(sample_dxf) + "],'warehouse.dxf',{type:'text/plain'})); input.files=transfer.files; input.dispatchEvent(new Event('change',{bubbles:true}));})()")
        browser.until("document.querySelector('.warehouse-dxf-options') !== null")
        browser.js("document.querySelector('.warehouse-dxf-options fieldset input').click()")
        browser.until("document.querySelector('.warehouse-dxf-preview') !== null")
        browser.js("document.querySelector('.warehouse-dxf-preview input').click()")
        browser.js("document.querySelector('.warehouse-dxf-preview button').click()")
        browser.until("document.querySelector('.warehouse-layout-footer').innerText.includes('контуры из DXF')")
        browser.js("document.querySelector('.warehouse-layout-map').scrollIntoView()")
        browser.screenshot("09-layout-dxf-mobile.png")
        print("WOW demo smoke OK; screenshots:", output)
    finally:
        browser.close()


if __name__ == "__main__":
    main()
