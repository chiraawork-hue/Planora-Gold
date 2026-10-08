#!/usr/bin/env python3
"""Fetch the publicly displayed EMASKU reference price, never a buyback quote."""
import json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

URL = "https://hartadinataabadi.co.id/"
out = Path("data/hartadinata-price.json")
req = urllib.request.Request(URL, headers={"User-Agent": "PlanoraGoldPriceMonitor/1.0", "Accept": "text/html"})
with urllib.request.urlopen(req, timeout=25) as response:
    html = response.read().decode("utf-8", errors="replace")
text = re.sub(r"<[^>]+>", " ", html)
text = re.sub(r"\s+", " ", text)
pattern = r"Harga\s+EMASKU\s+IDR\s+([\d.,]+)\s*/\s*gr.{0,140}?Last\s+update\s+(\d{1,2}:\d{2})\s+WIB\s+(\d{2}/\d{2}/\d{4})"
match = re.search(pattern, text, re.I)
if not match:
    raise SystemExit("No verified public EMASKU price and timestamp; preserving previous data")
price = int(re.sub(r"\D", "", match.group(1)))
if not 100000 <= price <= 10000000:
    raise SystemExit("Price outside validation range")
published = datetime.strptime(match.group(3) + " " + match.group(2), "%d/%m/%Y %H:%M").replace(tzinfo=ZoneInfo("Asia/Jakarta"))
now = datetime.now(timezone.utc)
if published > now.astimezone(ZoneInfo("Asia/Jakarta")):
    raise SystemExit("Source timestamp is in the future")
payload = {
    "brand": "Emasku", "type": "reference_price_per_gram",
    "price_idr_per_gram": price, "currency": "IDR",
    "source_updated_at": published.isoformat(),
    "fetched_at": now.isoformat(), "source_url": URL,
    "disclaimer": "Harga referensi EMASKU per gram dari situs resmi; bukan harga buyback atau harga transaksi per keping."
}
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Verified public reference price updated:", published.isoformat())
