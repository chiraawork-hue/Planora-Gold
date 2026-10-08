#!/usr/bin/env python3
"""Update EMASKU buyback only when official page exposes a dated table."""
import json,re,urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from html import unescape

URL="https://www.emasku.co.id/id/gold-price"
req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0 (compatible; PlanoraGold/1.0)"})
with urllib.request.urlopen(req,timeout=30) as response:
    html=response.read().decode("utf-8","replace")
plain=unescape(re.sub(r"<[^>]*>"," ",html))
plain=re.sub(r"\s+"," ",plain)
date_match=re.search(r"(?:Terakhir update|Last update).*?(\d{1,2}\s+(?:Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+\d{4})",plain,re.I)
months={name:i for i,name in enumerate("Januari Februari Maret April Mei Juni Juli Agustus September Oktober November Desember".split(),1)}
if not date_match: raise SystemExit("No source timestamp in server HTML; feed unchanged")
day,month,year=date_match.group(1).split()
date=datetime(int(year),months[month.capitalize()],int(day),tzinfo=ZoneInfo("Asia/Jakarta")).date()
if date>datetime.now(ZoneInfo("Asia/Jakarta")).date(): raise SystemExit("Future source date")
# Accept only the explicitly labeled Gold section, not Prime or product sale prices.
section=re.search(r"\bGold\b(.*?)\bPrime\b",plain,re.I)
if not section: raise SystemExit("No verifiable Gold buyback table; feed unchanged")
entries=[]
for grams,buy,bback in re.findall(r"(0\.1|0\.25|0\.5|1|2|5|10|25|50|100|125|150|175|200|250|500|1000)\s*gr\s*Rp\s*([\d.,]+)\s*Rp\s*([\d.,]+)",section.group(1),re.I):
    value=int(re.sub(r"\D","",bback))
    if not 100000<=value<=5000000000: raise SystemExit("Suspicious price")
    entries.append({"brand":"Emasku","grams":float(grams),"value":value,"date":date.isoformat(),"source":URL,"verified":True})
if len(entries)<5: raise SystemExit("Incomplete source table; feed unchanged")
path=Path("data/buyback.json")
data=json.loads(path.read_text(encoding="utf-8"))
keys={(q["brand"],q["grams"],q["date"]) for q in entries}
data["prices"]=[q for q in data["prices"] if (q.get("brand"),q.get("grams"),q.get("date")) not in keys]+entries
data["updatedAt"]=datetime.now(ZoneInfo("UTC")).isoformat()
path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("Imported verified EMASKU buyback quotes:",len(entries),date)
