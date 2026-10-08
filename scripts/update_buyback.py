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

def fetch_galeri24():
    """Galeri 24's own published buyback prices for Galeri 24 and Antam products.
    Antam quotes here are Galeri 24 outlet quotes, NOT Antam LM issuer buyback.
    """
    url = "https://galeri24.co.id/harga-emas"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 PlanoraGold/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read(4_000_000).decode("utf-8", errors="replace")
    parser = TextExtractor()
    parser.feed(html)
    content = " ".join(parser.parts)
    months = {"januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6,
              "juli": 7, "agustus": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12}
    result = []
    for label, brand in (("GALERI 24", "Galeri 24"),):
        heading = re.search(r"Harga\s+" + label + r"\s+Berat\s+Harga\s+Jual\s+Harga\s+Buyback", content, re.I)
        if not heading:
            raise RuntimeError(f"Galeri24 section missing: {label}")
        preceding = content[max(0, heading.start()-150):heading.start()]
        dates = list(re.finditer(r"Diperbarui\s+\w+,?\s+(\d{1,2})\s+(\w+)\s+(20\d{2})", preceding, re.I))
        if not dates or dates[-1].group(2).lower() not in months:
            raise RuntimeError(f"Galeri24 date missing: {label}")
        m = dates[-1]
        date = datetime(int(m.group(3)), months[m.group(2).lower()], int(m.group(1))).date()
        if abs((datetime.now().date() - date).days) > 7:
            raise RuntimeError(f"Galeri24 source stale: {label}: {date}")
        section = content[heading.end():heading.end()+3000].split("Diperbarui")[0]
        rows = re.findall(r"(0\.5|1|2|3|5|10|25|50|100|250|500|1000)\s+Rp\s*([\d.,]+)\s+Rp\s*([\d.,]+)", section)
        found = {}
        for weight, _retail, buyback in rows:
            grams = float(weight)
            value = int(re.sub(r"\D", "", buyback))
            if 100_000 * grams <= value <= 10_000_000 * grams:
                found[grams] = value
        if len(found) < 7:
            raise RuntimeError(f"Galeri24 buyback rows incomplete: {label}: {len(found)}")
        result.extend({"brand": brand, "grams": weight, "value": value, "date": date.isoformat(),
                       "source": url, "verified": True} for weight, value in sorted(found.items()))
    return result

def fetch_antam():
    """Read ANTAM LM's own official buyback price per gram, not its retail price."""
    url = "https://www.logammulia.com/id/sell/gold"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 PlanoraGold/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read(4_000_000).decode("utf-8", errors="replace")
    parser = TextExtractor()
    parser.feed(html)
    content = " ".join(parser.parts)
    match = re.search(r"Harga Buyback\s*:?\s*Rp\s*([\d.,]+)", content, re.I)
    stamp = re.search(r"Perubahan Terakhir\s*:?\s*(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})", content, re.I)
    months = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
    if not match or not stamp or stamp.group(2)[:3].lower() not in months:
        raise RuntimeError("ANTAM official buyback value/date missing")
    value = int(re.sub(r"\D", "", match.group(1)))
    date = datetime(int(stamp.group(3)), months[stamp.group(2)[:3].lower()], int(stamp.group(1))).date()
    if not 100_000 <= value <= 10_000_000 or abs((datetime.now().date()-date).days)>7:
        raise RuntimeError("ANTAM official buyback value/date outside validation limits")
    return [{"brand":"Antam","grams":grams,"value":round(value*grams),
             "date":date.isoformat(),"source":url,"verified":True}
            for grams in (0.5,1,2,3,5,10,25,50,100)]

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
    # Preserve existing verified data when the Galeri24 website changes.
    try:
        additional = fetch_galeri24()
        keys = {(p['brand'], p['grams'], p['date']) for p in additional}
        prices = [p for p in prices if (p.get('brand'), p.get('grams'), p.get('date')) not in keys]
        prices.extend(additional)
        print(f'Verified {len(additional)} Galeri24 buyback quotes')
    except Exception as exc:
        print(f'Galeri24 quotes unchanged (validation failed): {exc}')
    try:
        additional = fetch_antam()
        keys = {(p['brand'], p['grams'], p['date']) for p in additional}
        prices = [p for p in prices if (p.get('brand'), p.get('grams'), p.get('date')) not in keys]
        prices.extend(additional)
        print(f'Verified ANTAM LM issuer buyback quote for {additional[0]["date"]}')
    except Exception as exc:
        print(f'ANTAM LM quotes unchanged (validation failed): {exc}')
    # Retain a bounded history and never overwrite older verified observations.
    prices = sorted(prices, key=lambda p: p["date"])[-1500:]
    result = {"schema": 1, "updatedAt": datetime.now().isoformat(timespec="seconds") + "Z", "prices": prices,
              "note": "Official buyback prices, not guaranteed sale proceeds. Check fees and source date."}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {len(found)} UBS denominations for {date}")

if __name__ == "__main__":
    main()
