#!/usr/bin/env python3
"""Fetch explicitly dated 1g EMASKU buyback from HRTA Gold homepage.
Do not infer other weights or relabel an old quote as today's.
"""
import json
import re
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

URL = "https://www.emasku.co.id/id"
FILE = Path("data/buyback.json")

class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.hidden += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.hidden:
            self.hidden -= 1
    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data.strip())

def main():
    request = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (Planora Gold price reference)"})
    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", "replace")
    parser = VisibleText()
    parser.feed(html)
    page = re.sub(r"\\s+", " ", " ".join(parser.parts))
    # The homepage displays an explicit update timestamp (dd/mm/yy HH:MM:SS)
    # followed by "Harga Buyback" and a single 1-gram quote.
    match = re.search(
        r"Terakhir\\s+Update\\s+(\\d{1,2})/(\\d{1,2})/(\\d{2,4})\\s+\\d{1,2}:\\d{2}(?::\\d{2})?"
        r".{0,220}?Harga\\s+Buyback\\s+Rp\\s*([\\d.,]+)",
        page, re.IGNORECASE,
    )
    if not match:
        raise RuntimeError("HRTA homepage did not expose a dated 1g buyback quote. No price saved; manual entry remains available.")
    day, month, year, amount = match.groups()
    year = int(year)
    if year < 100:
        year += 2000
    date = datetime(year, int(month), int(day)).date().isoformat()
    value = int(re.sub(r"\\D", "", amount))
    if not 100000 <= value <= 20000000:
        raise RuntimeError("Unreasonable buyback amount; refusing to save.")
    quote = {"brand": "Emasku", "grams": 1, "value": value, "date": date, "source": URL, "verified": True}
    feed = json.loads(FILE.read_text(encoding="utf-8"))
    old = feed.get("prices", [])
    merged = [q for q in old if not (q.get("brand") == "Emasku" and float(q.get("grams", 0)) == 1 and q.get("date") == date)]
    merged.append(quote)
    if merged != old:
        feed["prices"] = merged
        feed["updatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        FILE.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    print(f"EMASKU official 1g buyback: Rp{value:,}; published {date}; {'updated' if merged != old else 'unchanged'}.")
    print("Other weights require their own official buyback quotes and are not estimated.")

if __name__ == "__main__":
    main()
