from __future__ import annotations
import html,json,re
from concurrent.futures import ThreadPoolExecutor,as_completed
import requests
from config import CACHE_DIR
DIR=CACHE_DIR/"industry_chain";UA={"User-Agent":"Mozilla/5.0 tw-stock-dashboard/6.0","Accept-Language":"zh-TW,zh;q=0.9","Accept":"text/html,*/*"}

def clean(s):
    x=html.unescape(str(s or "")).replace("　"," ");x=re.sub(r"\s+"," ",x).strip();x=re.split(r"使用條款|隱私權保護說明|網站地圖|相關連結|回到首頁",x)[0].strip();return re.sub(r"[、,，|｜]\s*$","",x).strip()

def looks_mojibake(v):
    s=str(v or "");marks=("å","é","æ","ç","è","ä","ï","ð","Â","Ã")
    return sum(s.count(x) for x in marks)>=2

def parse(text):
    s=re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>"," ",text,flags=re.I);s=re.sub(r"<(br|/p|/div|/h\d|/li|/tr)>","\n",s,flags=re.I);s=re.sub(r"<[^>]+>"," ",s);s=html.unescape(s).replace("\r","\n");s=re.sub(r"[\t ]+"," ",s);s=re.sub(r"\n+","\n",s)
    mains=[];leaves=[]
    for line in s.splitlines():
        if "►" not in line:continue
        p=[clean(x) for x in line.split("►",1)[1].strip().split(">")];p=[x for x in p if x and not looks_mojibake(x)]
        if p and p[0] not in mains:mains.append(p[0])
        if len(p)>=2:
            leaf=clean(" > ".join(p[1:]))
            if leaf and leaf not in leaves:leaves.append(leaf)
    return {"subIndustry":"、".join(mains) if mains else "—","theme":"、".join(leaves) if leaves else "—"}

def one(code):
    DIR.mkdir(parents=True,exist_ok=True);p=DIR/f"{code}.json"
    if p.exists():
        try:
            old=json.loads(p.read_text(encoding="utf-8"))
            if not looks_mojibake((old or {}).get("subIndustry","")) and not looks_mojibake((old or {}).get("theme","")):return code,old
        except:pass
    try:
        r=requests.get(f"https://ic.tpex.org.tw/company_chain.php?stk_code={code}",headers=UA,timeout=20);r.raise_for_status()
        try:text=r.content.decode("utf-8")
        except UnicodeDecodeError:text=r.content.decode("big5",errors="replace")
        x=parse(text);p.write_text(json.dumps(x,ensure_ascii=False),encoding="utf-8");return code,x
    except:return code,{"subIndustry":"—","theme":"—"}

def enrich(rows):
    need=[str(x["code"]) for x in rows];out={}
    with ThreadPoolExecutor(max_workers=8) as ex:
        fs=[ex.submit(one,c) for c in need]
        for f in as_completed(fs):
            c,x=f.result();out[c]=x
    for r in rows:r.update(out.get(str(r["code"]),{"subIndustry":"—","theme":"—"}))
    return rows
