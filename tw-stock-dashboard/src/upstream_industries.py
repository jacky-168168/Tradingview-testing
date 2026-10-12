"""Listed/OTC upstream industry map built from dated local stock archive + TPEx company-chain memberships.
Stage vocabulary is strictly restricted to verified '上游' labels in TPEx industry introductions.
A stock can belong to several upstream subcategories/industries; no prices or classification is invented.
"""
from __future__ import annotations
import concurrent.futures,html,json,re,time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from config import DATA_DIR,CACHE_DIR
from industry_chain import clean,looks_mojibake

SOURCE="https://ic.tpex.org.tw/"
OUT=DATA_DIR/"industry_upstream"/"latest.json"
CACHE=CACHE_DIR/"upstream_company"
USER_AGENT={"User-Agent":"Mozilla/5.0 (compatible; tw-stock-dashboard upstream industry research)","Accept-Language":"zh-TW,zh;q=0.9"}
# A second, independently cited supply-chain definition: semiconductor-grade wafer MATERIAL
# suppliers to fabs. TPEx's chip-design->wafer fabrication flow instead labels the
# separate stage "晶圓製造" as midstream. Do not misclassify all fabs as material suppliers.
WAFER_MATERIAL_SOURCE="https://www.itis.org.tw/NetReport_Detail.aspx?rpno=613160445"
WAFER_MATERIALS={"6488":"環球晶","3532":"台勝科","6182":"合晶","3016":"嘉晶"}
SOLAR_MATERIAL_SOURCE="https://ampletec.com.tw/about.asp"
# Verified upstream segment vocabulary from TPEx official "產業價值鏈資訊平台" industry charts.
# IMPORTANT: These are NOT the TWSE top-level industry labels.
INDUSTRIES=[
 {"name":"半導體","code":"D000","keys":["半導體"],"groups":[
   ("IP設計／IC設計代工",["IP設計/IC設計代工服務","IP設計/IC設計","IP設計","IC設計代工服務"]),
   ("IC 設計",["IC設計","消費性IC","微控制器IC","電源管理IC","平面顯示器控制IC","平面顯示器驅動IC","影像感測IC","類比IC","數位IC","記憶體IC","通訊IC","射頻IC","驅動IC","ASIC","網路IC"]),
   ("半導體用矽晶圓／磊晶材料（延伸上游）",[])]},
 {"name":"印刷電路板（PCB）","code":"L000","keys":["印刷電路板"],"groups":[
   ("玻璃纖維／玻纖布",["玻璃纖維/玻纖布","玻璃纖維","玻纖布"]),
   ("環氧樹脂",["環氧樹脂"]),("酚醛樹脂",["酚醛樹脂"]),
   ("銅箔",["銅箔"]),("聚亞醯胺樹脂",["聚亞醯胺樹脂","聚醯亞胺樹脂","PI樹脂"]),
   ("製程與檢測設備",["生產製程及檢測設備"])]},
 {"name":"通信網路","code":"I000","keys":["通信網路"],"groups":[
   ("網路 IC",["網路IC"]),("微處理器",["微處理器"]),("記憶體",["記憶體"]),
   ("主／被動元件",["主/被動元件","主被動元件"]),
   ("印刷電路板",["印刷電路板"]),
   ("塑膠／金屬機殼",["塑膠/金屬機殼","塑膠/金屬機殼及散熱片"]),
   ("網路線材",["線材","網路線材"]),("其他通訊零組件",["其他零組件"])]},
 {"name":"電腦及週邊設備","code":"F000","keys":["電腦及週邊設備","電腦及週邊設備產業"],"groups":[
   ("中央處理器",["中央處理器"]),("晶片組",["晶片組"]),("面板",["面板"]),
   ("顯示器模組",["顯示器模組"]),("記憶體",["記憶體"]),("主機板",["主機板"]),
   ("機殼",["機殼"]),("電源供應器",["電源供應器"]),("網路卡",["網路卡"]),
   ("電池",["電池"]),("散熱與風扇",["散熱片、風扇馬達、散熱模組","散熱片/風扇馬達/散熱模組"]),
   ("輸出入模組／介面卡",["輸出入模組/介面卡","輸出/入模組/介面卡"]),
   ("顯示卡",["顯示卡"]),("硬碟／儲存系統",["硬碟機","磁碟儲存系統"]),
   ("BIOS／嵌入式軟體",["BIOS(嵌入式軟體)","BIOS"]),
   ("隨身碟與讀卡機",["隨身碟、記憶卡讀卡機"]),
   ("多功能視訊卡",["多功能視訊卡"]),("鏡片與鏡頭",["光學鏡片、鏡頭"]),
   ("連接線",["連接線"]),("機構樞紐",["機構樞紐"]),
   ("金屬／塑膠模具",["金屬、塑膠模具"]),("其他電腦零組件",["其他電腦及週邊設備之零組件"])]},
 {"name":"連接器","code":"K000","keys":["連接器"],"groups":[
   ("金屬材料",["金屬材料"]),("電鍍材料",["電鍍材料"]),("塑膠材料",["塑膠材料"]),
   ("其他材料",["其他材料","其他材料(如鋅合金、陶瓷、玻璃)"])]},
 {"name":"汽車","code":"3000","keys":["汽車"],"groups":[
   ("車燈",["車燈"]),("輪胎",["輪胎"]),("鈑金",["鈑金"]),
   ("鋁合金鋼圈",["鋁合金鋼圈"]),("引擎蓋",["引擎蓋"]),
   ("保險桿",["保險桿"]),("其他汽車零配件",["其他"])]},
 {"name":"太陽能","code":"A100","keys":["太陽能產業"],"groups":[
   ("太陽能材料（跨產業應用）",["材料"]),("矽晶圓／矽晶片",["矽晶圓/矽晶片","矽晶圓","矽晶片"])]},
 {"name":"電動車輛","code":"A300","keys":["電動車輛產業","電動車產業"],"groups":[
   ("鋰電池材料",["鋰電池材料"])]},
]
def normalize(s):
    s=str(s or "").strip()
    return re.sub(r"[\s　\n\r、,，／/（）()\-_]+","",s).casefold()

def read_memberships(markup):
    text=re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>"," ",markup,flags=re.I)
    text=re.sub(r"<(br|/p|/div|/h\d|/li|/tr)>","\n",text,flags=re.I)
    text=re.sub(r"<[^>]+>"," ",text)
    text=html.unescape(text).replace("\r","\n")
    text=re.sub(r"[\t ]+"," ",text)
    found=[];seen=set()
    for line in text.splitlines():
        if "►" not in line:continue
        parts=[clean(x) for x in line.split("►",1)[1].split(">")]
        if len(parts)<2 or looks_mojibake(" ".join(parts)):continue
        sector,leaf=parts[0]," > ".join(parts[1:])
        if not sector or not leaf or "查無" in leaf:continue
        key=(sector,leaf)
        if key not in seen:found.append({"industry":sector,"subCategory":leaf});seen.add(key)
    return found

def fetch_company(code):
    CACHE.mkdir(parents=True,exist_ok=True)
    target=CACHE/(code+".json")
    if target.exists():
        try:
            j=json.loads(target.read_text(encoding="utf-8"))
            if j.get("ok") is True and isinstance(j.get("entries"),list):return j["entries"],True
        except (OSError,ValueError):pass
    url=SOURCE+"company_chain.php?stk_code="+code
    for i in range(2):
        try:
            r=requests.get(url,headers=USER_AGENT,timeout=14)
            r.raise_for_status()
            try:page=r.content.decode("utf-8")
            except UnicodeDecodeError:page=r.content.decode("big5",errors="replace")
            entries=read_memberships(page)
            # A valid company page can be unclassified, but should at least mention the query code.
            if code not in page or ("所屬產業鏈" not in page and "公司所屬產業鏈" not in page):
                raise ValueError("company chain page missing identifier/heading")
            target.write_text(json.dumps({"ok":True,"entries":entries},ensure_ascii=False),encoding="utf-8")
            return entries,True
        except (requests.RequestException,ValueError,UnicodeError):
            if i==0:time.sleep(0.8)
    return [],False

def stage_group(definition,subcategory):
    name=normalize(subcategory)
    # Match only documented upstream stage labels exactly, never guesses such as
    # "other IC" or unrelated wafer-fab stages just because text contains "IC".
    for group,labels in definition["groups"]:
        if name and name in {normalize(x) for x in labels}:return group
    return None

def compile_map(stocks,memberships,data_date):
    groups={}
    for spec in INDUSTRIES:
        groups[spec["code"]]={"name":spec["name"],"code":spec["code"],
            "source":SOURCE+"introduce.php?ic="+spec["code"],"subgroups":{}}
    covered=0;upstream_stocks=set();entries_count=0
    published_materials=set();basis_counts={"tpex_official":0,"independent_industry_material":0}
    for x in stocks:
        code=str(x.get("code") or "").strip();market=x.get("market")
        if market not in ("上市","上櫃") or not re.fullmatch(r"[0-9]{4}",code):continue
        source=memberships.get(code)
        if source is None:continue
        covered+=1
        matches={}
        for entry in source:
            sector=normalize(entry.get("industry",""))
            for spec in INDUSTRIES:
                if sector not in [normalize(k) for k in spec["keys"]]:continue
                group=stage_group(spec,entry.get("subCategory",""))
                if group:
                    matches[(spec["code"],group)]={
                        "classification":"櫃買中心上游階段","basis":"tpex_official",
                        "source":SOURCE+"company_chain.php?stk_code="+code,
                        "roleNote":"官方產業鏈列名；不代表該產品是公司主要營收來源。"}
        if code in WAFER_MATERIALS:
            expected=WAFER_MATERIALS[code]
            if normalize(expected) not in normalize(x.get("name")):
                raise RuntimeError(f"Silicon wafer material code/name conflict for {code}: {x.get('name')!r}")
            matches[("D000","半導體用矽晶圓／磊晶材料（延伸上游）")]={
                "classification":"半導體材料供應鏈（延伸）","basis":"independent_industry_material",
                "source":WAFER_MATERIAL_SOURCE,
                "roleNote":"工研院 ITIS 列為晶圓廠的半導體矽晶圓／磊晶材料供應商；與太陽能矽晶片、晶圓代工製程分層不同。"}
            published_materials.add(code)
        for (sid,segment),meta in sorted(matches.items()):
            upstream_stocks.add((market,code));entries_count+=1
            basis_counts[meta["basis"]]+=1
            row={k:x.get(k) for k in ("code","name","market","industry","close","ret5","ret20","momentumScore","turnoverB","models")}
            row["models"]=row.get("models") or []
            row.update(meta)
            if code=="4760" and sid=="A100":
                row["roleNote"]="勤凱：官方太陽能材料上游供應商，官網確認太陽能電池背銀導電漿用途；亦供應被動元件與IC封裝，非純太陽能股。"
                row["extraSource"]=SOLAR_MATERIAL_SOURCE
            groups[sid]["subgroups"].setdefault(segment,[]).append(row)
    sectors=[]
    for spec in INDUSTRIES:
        item=groups[spec["code"]];child=[]
        for key,_ in spec["groups"]:
            seen=set();items=[]
            for x in item["subgroups"].get(key,[]):
                token=(x["market"],x["code"])
                if token in seen:continue
                seen.add(token);items.append(x)
            items.sort(key=lambda x:(-(float(x["momentumScore"]) if x["momentumScore"] is not None else -999),x["code"]))
            extended=spec["code"]=="D000" and key.startswith("半導體用矽晶圓")
            solar=spec["code"]=="A100" and key.startswith("太陽能材料")
            note=("另依工研院 ITIS 矽晶圓材料研究補充。此為晶圓廠『材料供應鏈上游』，不同於櫃買中心以 IP／IC 設計為上游的製造流程分層。"
                  if extended else "櫃買中心將太陽能漿料等材料列在此上游；公司可能跨足其他領域，並非太陽能營收比重排名。" if solar else "")
            child.append({"name":key,"count":len(items),"stocks":items,"source":WAFER_MATERIAL_SOURCE if extended else item["source"],"note":note,
                          "classification":"獨立研究延伸上游材料" if extended else "櫃買中心官方上游"})
        item["subgroups"]=child
        item["stockCount"]=len({(z["market"],z["code"]) for g in child for z in g["stocks"]})
        sectors.append(item)
    valid=len([x for x in stocks if x.get("market") in ("上市","上櫃")])
    return {"schema":"tw-upstream-industries-v2","dataDate":data_date,
        "generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "source":"TPEx official company_chain.php & introduce.php, ITIS wafer materials research, dated full-market stock diagnostics",
        "method":"TPEx sector plus documented upstream stage, supplemented ONLY by named ITIS semiconductor-grade silicon wafer suppliers. Stage != main revenue exposure. Solar PV silicon wafers are NOT semiconductor fab wafers.",
        "coverage":{"marketStocks":valid,"verifiedCompanyPages":covered,"verifiedRatioPct":round(100*covered/valid,1) if valid else 0,
                    "distinctUpstreamStocks":len(upstream_stocks),"upstreamMemberships":entries_count,"industries":len(sectors),
                    "classifiedBySource":basis_counts},
        "audit":{"stageReferences":{i["code"]:SOURCE+"introduce.php?ic="+i["code"] for i in INDUSTRIES},
                 "extendedMaterials":sorted(published_materials),
                 "materialsReference":WAFER_MATERIAL_SOURCE,
                 "solarConductivePasteReference":SOLAR_MATERIAL_SOURCE,
                 "qualification":"TPEx official category is a value-chain ROLE, not stock principal-business or segment revenue share."},
        "industries":sectors}

def main():
    inp=DATA_DIR/"stocks"/"latest.json"
    data=json.loads(inp.read_text(encoding="utf-8"))
    if data.get("schema") not in ("stock-diagnostics-v1","stock-diagnostics-v2") or not isinstance(data.get("stocks"),list) or len(data["stocks"])<1000:
        raise RuntimeError("Full-market dated diagnostic archive unavailable; no partial G-model fallback")
    stocks=data["stocks"];date=str(data["dataDate"]);ids=sorted({str(z["code"]) for z in stocks if z.get("market") in ("上市","上櫃")})
    entries={};fail=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        jobs={pool.submit(fetch_company,c):c for c in ids}
        for i,f in enumerate(concurrent.futures.as_completed(jobs),1):
            code=jobs[f];items,ok=f.result()
            if ok:entries[code]=items
            else:fail.append(code)
            if i%200==0:print("TPEx industry-chain verified",i,"/",len(ids),"ok",len(entries),"failed",len(fail),flush=True)
    result=compile_map(stocks,entries,date)
    result["coverage"]["failedCompanyPages"]=len(fail)
    print("Upstream coverage",json.dumps(result["coverage"],ensure_ascii=False),flush=True)
    if "6488" in ids and "6488" not in result["audit"]["extendedMaterials"]:
        raise RuntimeError("GlobalWafers 6488 MUST appear in semiconductor-grade material suppliers")
    if result["coverage"]["verifiedCompanyPages"]<max(500,int(len(ids)*.5)) or result["coverage"]["distinctUpstreamStocks"]<30:
        raise RuntimeError("Insufficient official company-chain coverage; refuse to publish misleading zero-sector data")
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print("Published",OUT,"date",date,"sectors",{x["name"]:x["stockCount"] for x in result["industries"]},flush=True)
if __name__=="__main__":main()
