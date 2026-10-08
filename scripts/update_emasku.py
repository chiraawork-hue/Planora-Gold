#!/usr/bin/env python3
"""Merge dated EMASKU/HRTA Gold buyback quotes into Planora's shared feed."""
import json, re, urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

URL = "https://www.emasku.co.id/id/gold-price"
FILE = Path("data/buyback.json")
class TextTable(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows=[]; self.row=None; self.cell=None; self.parts=[]; self.text=[]
    def handle_starttag(self, tag, attrs):
        if tag=="tr": self.row=[]
        if tag in ("td","th") and self.row is not None: self.cell=[]
    def handle_data(self, data):
        self.text.append(data)
        if self.cell is not None: self.cell.append(data)
    def handle_endtag(self, tag):
        if tag in ("td","th") and self.cell is not None:
            self.row.append(" ".join(self.cell).strip()); self.cell=None
        if tag=="tr" and self.row is not None:
            self.rows.append(self.row); self.row=None
def rupiah(s):
    digits=re.sub(r"[^0-9]","",s)
    return int(digits) if digits else 0
def main():
    req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0 (compatible; PlanoraGold/1.0)"})
    with urllib.request.urlopen(req,timeout=25) as resp: html=resp.read().decode("utf-8","replace")
    p=TextTable(); p.feed(html)
    full=" ".join(p.text)
    match=re.search(r"(?:Terakhir\s+update|Tanggal)\s*(?:Tanggal\s*)?(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})",full,re.I)
    months={"januari":1,"februari":2,"maret":3,"april":4,"mei":5,"juni":6,"juli":7,"agustus":8,"september":9,"oktober":10,"november":11,"desember":12}
    if not match or match.group(2).lower() not in months:
        raise RuntimeError("Source publication date not found: refuse to mislabel old prices as today's.")
    day,month,year=match.groups()
    date=f"{int(year):04d}-{months[month.lower()]:02d}-{int(day):02d}"
    quotes=[]
    for row in p.rows:
        if len(row)<3: continue
        g=re.match(r"^\s*(\d+(?:[.,]\d+)?)\s*(?:gr|gram)\b",row[0],re.I)
        if not g: continue
        grams=float(g.group(1).replace(",","."))
        buyback=rupiah(row[2])
        if buyback>1000:
            quotes.append({"brand":"Emasku","grams":grams,"value":buyback,"date":date,"source":URL,"verified":True})
    # Gold and Prime can list same weight: keep first (Gold) only.
    quotes=list({q["grams"]:q for q in reversed(quotes)}.values())
    if len(quotes)<5: raise RuntimeError(f"Only {len(quotes)} quotes parsed; refusing to update.")
    feed=json.loads(FILE.read_text(encoding="utf-8"))
    old=feed.get("prices",[])
    keys={(q["brand"],float(q["grams"]),q["date"]) for q in quotes}
    merged=[q for q in old if (q.get("brand"),float(q.get("grams",0)),q.get("date")) not in keys]+quotes
    if merged!=old:
        feed["prices"]=merged
        feed["updatedAt"]=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
        FILE.write_text(json.dumps(feed,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"EMASKU source date {date}; {len(quotes)} verified weights; feed {'updated' if merged!=old else 'unchanged'}.")
if __name__=="__main__": main()
