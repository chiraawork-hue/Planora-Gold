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
    """Read Galeri24 outlet buyback quotes for Galeri24, Antam and Lotus Archi."""
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
    for label, brand in (("GALERI 24", "Galeri 24"), ("ANTAM", "Antam"), ("LOTUS ARCHI", "Lotus")):
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
        if len(found) < (5 if brand == "Lotus" else 7):
            raise RuntimeError(f"Galeri24 buyback rows incomplete: {label}: {len(found)}")
        result.extend({"brand": brand, "grams": weight, "value": value, "date": date.isoformat(),
                       "source": url, "verified": True} for weight, value in sorted(found.items()))
    return result

def fetch_emasku():
    """Use HRTA Gold's published buyback per gram only with a verifiable recent date."""
    url = "https://hrtagold.id/id"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 PlanoraGold/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read(4_000_000).decode("utf-8", errors="replace")
    parser = TextExtractor()
    parser.feed(html)
    content = " ".join(parser.parts)
    stamp = re.search(r"Terakhir\s+Update\s+(\d{2})/(\d{2})/(\d{2,4})", content, re.I)
    match = re.search(r"Harga\s+Buyback\s+Rp\s*([\d.,]+)", content, re.I)
    if not stamp or not match:
        raise RuntimeError("HRTA official buyback price or update date missing")
    year = int(stamp.group(3))
    if year < 100:
        year += 2000
    date = datetime(year, int(stamp.group(2)), int(stamp.group(1))).date()
    value = int(re.sub(r"\D", "", match.group(1)))
    if abs((datetime.now().date()-date).days) > 7:
        raise RuntimeError(f"HRTA source is stale: {date}")
    if not 100_000 <= value <= 10_000_000:
        raise RuntimeError("HRTA buyback price failed validation")
    return [{"brand":"Emasku","grams":grams,"value":round(value*grams),
             "date":date.isoformat(),"source":url,"verified":True}
            for grams in (0.5,1,2,5,10,25,50,100)]

def fetch_antam():
    """Read issuer buyback per gram; fail closed if official data cannot be verified."""
    import urllib.error
    urls = ("https://www.logammulia.com/id/sell/gold",
            "https://logammulia.com/id/sell/gold")
    failures = []
    for url in urls:
        try:
            request = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
            })
            with urllib.request.urlopen(request, timeout=30) as response:
                html = response.read(4_000_000).decode("utf-8", errors="replace")
            parser = TextExtractor()
            parser.feed(html)
            content = " ".join(parser.parts)
            # Input controls can interrupt the text between the label and price.
            match = re.search(r"Harga\s+Buyback\s*:\s*(?:\[?Input\]?\s*)?Rp\s*([\d.,]+)", content, re.I)
            stamp = re.search(r"Perubahan\s+Terakhir\s*:\s*(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})", content, re.I)
            months = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
                      "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
            if not match or not stamp or stamp.group(2)[:3].lower() not in months:
                raise RuntimeError(f"buyback or timestamp absent (page text length {len(content)}; price={bool(match)}; date={bool(stamp)})")
            value = int(re.sub(r"\D", "", match.group(1)))
            date = datetime(int(stamp.group(3)), months[stamp.group(2)[:3].lower()], int(stamp.group(1))).date()
            if not 100_000 <= value <= 10_000_000 or abs((datetime.now().date()-date).days) > 7:
                raise RuntimeError(f"buyback value/date failed validation: {value}, {date}")
            print(f"ANTAM LM official source: {url}; buyback Rp {value:,}/g; dated {date}")
            return [{"brand":"Antam","grams":grams,"value":round(value*grams),
                     "date":date.isoformat(),"source":url,"verified":True}
                    for grams in (0.5,1,2,3,5,10,25,50,100)]
        except Exception as exc:
            failures.append(f"{url}: {type(exc).__name__}: {exc}")
    raise RuntimeError("; ".join(failures))

def main():
    previous = json.loads(OUT.read_text(encoding="utf-8"))
    prices = previous.get("prices", [])
    results = {}

    def merge(brand, fetcher):
        nonlocal prices
        try:
            additional = fetcher()
            if not additional:
                raise RuntimeError("No verified prices returned")
            keys = {(p["brand"], p["grams"], p["date"]) for p in additional}
            prices = [p for p in prices if (p.get("brand"), p.get("grams"), p.get("date")) not in keys]
            prices.extend(additional)
            results[brand] = f"OK: {len(additional)} verified quotes"
        except Exception as exc:
            results[brand] = f"STALE: {type(exc).__name__}: {exc}"
        print(f"{brand}: {results[brand]}")

    def fetch_ubs():
        request = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 PlanoraGoldPriceVerifier/1.0"})
        with urllib.request.urlopen(request, timeout=25) as response:
            html = response.read(3_000_000).decode("utf-8", errors="replace")
        parser = TextExtractor()
        parser.feed(html)
        content = " ".join(parser.parts)
        section = content.find("Harga BuyBack UBS Gold Bar")
        if section < 0:
            raise RuntimeError("Official UBS buyback table not found")
        snippet = content[section:section + 8500]
        match = re.search(r"Updated\s+Date\s+(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})", snippet, re.I)
        months = {"january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
                  "july":7,"august":8,"september":9,"october":10,"november":11,"december":12}
        if not match or match.group(2).lower() not in months:
            raise RuntimeError("UBS source date cannot be verified")
        date = datetime(int(match.group(3)), months[match.group(2).lower()], int(match.group(1))).date()
        if abs((datetime.now().date() - date).days) > 7:
            raise RuntimeError(f"UBS source date stale: {date}")
        row = re.compile(r"(0\.5|1|2|3|4|5|10|25|50|100)\s*Gram\s+Rp\s*([\d.,]+)\s+Rp\s*([\d.,]+)", re.I)
        found = {}
        for weight, _retail, buyback in row.findall(snippet):
            grams = float(weight)
            value = int(re.sub(r"\D", "", buyback))
            if grams in WEIGHTS and 100_000 * grams <= value <= 10_000_000 * grams:
                found[grams] = value
        if len(found) < 7:
            raise RuntimeError("Insufficient verified UBS prices")
        return [{"brand":"UBS","grams":grams,"value":value,"date":date.isoformat(),
                 "source":URL,"verified":True} for grams,value in sorted(found.items())]

    merge("UBS", fetch_ubs)

    def fetch_galeri_group():
        return fetch_galeri24()
    # These three brands share one official Galeri24 source and validation.
    try:
        additional = fetch_galeri_group()
        for brand in ("Galeri 24", "Lotus", "Antam"):
            subset = [p for p in additional if p["brand"] == brand]
            if not subset:
                results[brand] = "STALE: No verified quotes"
                print(f"{brand}: {results[brand]}")
                continue
            keys = {(p["brand"], p["grams"], p["date"]) for p in subset}
            prices = [p for p in prices if (p.get("brand"),p.get("grams"),p.get("date")) not in keys]
            prices.extend(subset)
            results[brand] = f"OK: {len(subset)} verified quotes"
            print(f"{brand}: {results[brand]}")
    except Exception as exc:
        for brand in ("Galeri 24", "Lotus"):
            results[brand] = f"STALE: {type(exc).__name__}: {exc}"
            print(f"{brand}: {results[brand]}")

    merge("Emasku", fetch_emasku)
    prices = sorted(prices, key=lambda p: p["date"])[-1500:]
    if prices != previous.get("prices", []):
        result = {"schema":1, "updatedAt":datetime.now().astimezone().isoformat(),
                  "prices":prices, "note":previous.get("note", "Official buyback reference; check source dates.")}
        OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        print("No verified price changes; previous file preserved")
    if not any(v.startswith("OK:") for v in results.values()):
        raise SystemExit("All price sources failed verification; old prices preserved")

if __name__ == "__main__":
    main()
