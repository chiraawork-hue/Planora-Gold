#!/usr/bin/env python3
"""Capture HRTA GOLD buyback table rendered in a real browser; fail closed."""
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

URL = "https://hrtagold.id/id/gold-price"
WEIGHTS = [0.1,0.25,0.5,1,2,5,10,25,50,100,125,150,175,200,250,500,1000]
def rupiah(value):
    digits = re.sub(r"[^0-9]", "", value)
    return int(digits) if digits else 0

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(locale="id-ID", timezone_id="Asia/Jakarta")
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.locator("table").first.wait_for(timeout=30000)
    page.wait_for_timeout(5000)
    print("Rendered table count:", page.locator("table").count())
    tables = page.locator("table")
    records = []
    for t in range(tables.count()):
        table = tables.nth(t)
        headings = " ".join(table.locator("th").all_text_contents()).lower()
        print("Table", t, "headers:", headings[:240])
        if not ("buyback" in headings and ("berat" in headings or "gr" in headings)):
            continue
        in_gold = False
        for row in table.locator("tr").all():
            row_text = re.sub(r"\s+", " ", row.inner_text()).strip()
            if re.fullmatch(r"GOLD", row_text, re.I):
                in_gold = True
                continue
            if in_gold and re.fullmatch(r"(?:PRIME|SILVER|PLATINUM|GOLD PRIME|EMASKU PRIME)", row_text, re.I):
                in_gold = False
                continue
            if not in_gold:
                continue
            cells = [re.sub(r"\s+", " ", v).strip() for v in row.locator("td").all_text_contents()]
            if not cells: continue
            # Table can split 'Rp' and number into separate cells.
            values = [v for v in cells if v.lower() != "rp" and v]
            if len(values) < 3: continue
            m = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*gr", values[0], re.I)
            if not m: continue
            weight = float(m.group(1).replace(",", "."))
            if weight not in WEIGHTS: continue
            purchase, buyback = rupiah(values[1]), rupiah(values[2])
            if not (100000 <= buyback <= purchase <= 5000000000):
                raise SystemExit("Invalid buyback / purchase prices; previous feed preserved")
            records.append((weight, purchase, buyback))
    print("Selected GOLD rows:", len(records), "weights:", [r[0] for r in records])
    browser.close()

if set(w for w, _, _ in records) != set(WEIGHTS) or len(records) != len(WEIGHTS):
    raise SystemExit(f"Expected 17 unique GOLD rows; got {len(records)}. Previous feed preserved.")
now = datetime.now(ZoneInfo("Asia/Jakarta"))
date = now.date().isoformat()
path = Path("data/buyback.json")
data = json.loads(path.read_text(encoding="utf-8"))
# Observed-at date, not claimed as source publication date.
entries = [
    {"brand":"Emasku","grams":weight,"value":buyback,"purchaseReference":purchase,
     "date":date,"source":URL,"verified":True,
     "observedAt":now.isoformat(),"verificationNote":"Direct browser observation of official HRTA Gold GOLD table; date is observation date."}
    for weight,purchase,buyback in records
]
keys = {(q["brand"],q["grams"],q["date"]) for q in entries}
data["prices"] = [q for q in data["prices"] if (q.get("brand"),q.get("grams"),q.get("date")) not in keys] + entries
data["updatedAt"] = now.isoformat()
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"SUCCESS: {len(entries)} EMASKU buyback quotes observed {now.isoformat()}")
