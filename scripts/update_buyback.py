"""Fetch UBS official buyback table. Fail closed if its layout changes."""
import json
import re
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

URL = "https://ubslifestyle.com/harga-buyback-hari-ini/"
OUT = Path("data/buyback.json")
WEIGHTS = {0.5, 1, 2, 3, 4, 5, 10, 25, 50, 100}

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, data):
        value = " ".join(data.split())
        if value:
            self.parts.append(value)

def main():
    request = urllib.request.Request(URL, headers={"User-Agent": "PlanoraGoldPriceVerifier/1.0"})
    with urllib.request.urlopen(request, timeout=25) as response:
        html = response.read(3_000_000).decode("utf-8", errors="replace")
    parser = TextExtractor()
    parser.feed(html)
    text = " ".join(parser.parts)
    # Require the actual buyback section and an unambiguous update date.
    section = text.find("Harga BuyBack UBS Gold Bar")
    if section < 0:
        raise RuntimeError("Official buyback table not found; no prices published.")
    snippet = text[section:section + 8500]
    match = re.search(r"Updated\s+Date\s+(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})", snippet, re.I)
    months = {"january": 1, "february": 2, "march": 3, "april": 4,
              "may": 5, "june": 6, "july": 7, "august": 8,
              "september": 9, "october": 10, "november": 11, "december": 12}
    if not match or match.group(2).lower() not in months:
        raise RuntimeError("Source date cannot be verified.")
    date = datetime(int(match.group(3)), months[match.group(2).lower()], int(match.group(1))).date()
    if abs((datetime.now().date() - date).days) > 7:
        raise RuntimeError("Source date is stale or in the future.")
    # Each row: weight, retail purchase price, official buyback price.
    row = re.compile(r"(0\.5|1|2|3|4|5|10|25|50|100)\s*Gram\s+Rp\s*([\d.,]+)\s+Rp\s*([\d.,]+)", re.I)
    found = {}
    for weight, _retail, buyback in row.findall(snippet):
        w = float(weight)
        value = int(re.sub(r"\D", "", buyback))
        if w in WEIGHTS and 100_000 * w <= value <= 10_000_000 * w:
            found[w] = value
    if len(found) < 7:
        raise RuntimeError("Not enough valid UBS rows; refusing partial/unverified update.")
    previous = json.loads(OUT.read_text(encoding="utf-8"))
    prices = [p for p in previous.get("prices", []) if p.get("brand") != "UBS" or p.get("date") != date.isoformat()]
    for weight, value in sorted(found.items()):
        prices.append({"brand": "UBS", "grams": weight, "value": value, "date": date.isoformat(), "source": URL, "verified": True})
    # Retain a bounded history and never overwrite older verified observations.
    prices = sorted(prices, key=lambda p: p["date"])[-1500:]
    result = {"schema": 1, "updatedAt": datetime.now().isoformat(timespec="seconds") + "Z", "prices": prices,
              "note": "Official buyback prices, not guaranteed sale proceeds. Check fees and source date."}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {len(found)} UBS denominations for {date}")

if __name__ == "__main__":
    main()
