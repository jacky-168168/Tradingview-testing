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
# CPO is NOT a TPEx official industry code. This is a separate EVIDENCE-BASED
# thematic supply-chain upstream directory; avoid conflating any optical-module
# business with a confirmed Nvidia/Broadcom CPO order or with a pure-play revenue.
CPO_SOURCE="https://www.trendforce.com.tw/presscenter/news/20260727-13150.html"
CPO_GROUPS=[
    "InP／GaAs 磊晶及雷射材料（核心上游）",
    "FAU／光纖陣列與精密耦合（核心上游）",
    "外部雷射 ELS／光主動元件（上游供應）",
]
CPO_EVIDENCE={
    # Codes -> group, product relationship, cited public information.
    "3081":(CPO_GROUPS[0],"磷化銦光通訊雷射／檢光磊晶片；提供光源材料，不代表直接取得CPO訂單。","https://www.lmoc.com.tw/index.php?i=1&id=282&lang=cht&option=module&task=dfile"),
    "2455":(CPO_GROUPS[0],"三五族磊晶／光通訊 InP；屬光源材料上游，CPO客戶訂單須另行查證。","https://www.skis.com.tw/Report/education/KNW20260826.html"),
    "4991":(CPO_GROUPS[0],"InP／GaAs 三五族光電半導體製程；屬光源技術上游，非直接量產訂單證明。","https://www.skis.com.tw/Report/education/KNW20260826.html"),
    "4971":(CPO_GROUPS[0],"磷化銦光電材料與基板；依供應鏈延伸研究，營收占比未確認。","https://money.udn.com/money/story/5612/9526606"),
    "3363":(CPO_GROUPS[1],"CPO用FAU光纖陣列、耦光對位與高密度光連接；公司法說產品路線。","https://finmoconf.diveinvest.net/presentation/691c7285bab52fb5c8f0575f"),
    "3163":(CPO_GROUPS[1],"CPO平台光纖配線、FAU及光纖套件；產品已在公司法說揭露。","https://finmoconf.diveinvest.net/presentation/69b01a86bab52fb5c8bbe2c4"),
    "6442":(CPO_GROUPS[1],"高芯數光纖、CPO-ELS與FAU；部分透過轉投資公司布局，勿等同母公司所有產品已量產。","https://finmoconf.diveinvest.net/presentation/6a26cf94bab52fb5c81f8213"),
    "3234":(CPO_GROUPS[2],"光主動雷射、VCSEL及光偵測器；CPO相容光源供應鏈，直接客戶關係未確認。","https://www.truelight.com.tw/products/optical-communication/"),
    "3450":(CPO_GROUPS[2],"雷射二極體封裝及外置雷射光學次組件；屬CPO相關光源供應環節。","https://www.elaser.com.tw/sp2-4.htm"),
    "4979":(CPO_GROUPS[2],"光通訊 CW laser、主動晶粒及光學模組；按公開產業研究作為上游觀察，非證實直接CPO供應。","https://www.luxnetcorp.com.tw/news"),
    "4977":(CPO_GROUPS[2],"外置雷射ELSFP封裝及光收發器；公司公開資訊提及CPO相關產品布局。","https://www.moneydj.com/KMDJ/news/newsviewer.aspx?a=41a8b048-81d8-4b07-bc14-0c0998fa88b9"),
}

PASSIVE_INDUSTRY_SOURCE="https://ic.tpex.org.tw/introduce.php?ic=J000"
COMM_SOURCE="https://ic.tpex.org.tw/introduce.php?ic=I000"
# A distinct active/passive product split of TPEx communication "主/被動元件".
# Do NOT infer active vs passive from that parent TPEx label alone.
# Active optical lasers / PD chips, independently verified product disclosures:
COMM_ACTIVE_EVIDENCE={
    "3081":("光通訊雷射及光偵測磊晶片（主動）","https://www.lmoc.com.tw/index.php?i=1&id=282&lang=cht&option=module&task=dfile"),
    "3234":("雷射、VCSEL 與光偵測器（主動）","https://www.truelight.com.tw/products/optical-communication/"),
    "4908":("光收發模組（光主動）","https://www.apacoe.com.tw/files/111%E5%B9%B4%E8%82%A1%E6%9D%B1%E6%9C%83%E5%B9%B4%E5%A0%B1.pdf"),
    "4979":("光通訊主動晶粒及光收發模組","https://www.luxnetcorp.com.tw/news"),
    "3450":("光通訊雷射二極體 VCSEL、FP／DFB 及檢光器封裝（光主動）","https://www.elaser.com.tw/sp2-4.htm"),
}
# Independent product disclosures for communication passive/filters. TPEx J000
# memberships are preferred when available; these are supplemental evidence.
COMM_PASSIVE_EVIDENCE={
    "6284":("射頻濾波器、電感及磁珠","https://www.inpaq.com.tw/events-01.php?eventsID=174&secureChk=75cd6dd7a655fac1b503e18d9474dafc"),
    "3491":("微波、毫米波被動元件及濾波器","https://www.umt-tw.com/tw/about.php"),
    "3152":("高頻濾波器、巴倫、耦合器與射頻前端被動元件","https://www.acxc.com.tw/intro"),
    "6792":("壓電／天線及線路保護元件，含無線通訊被動零件","https://www.unictron.com/wp-content/uploads/2026/05/114%E5%B9%B4%E5%BA%A6%E5%B9%B4%E5%A0%B1%E4%B8%AD%E6%96%87.pdf"),
}
# Optically passive transport/fiber is not the same as RLC, and must not be
# inferred solely from a generic TPEx "communication equipment" label.
COMM_PASSIVE_STAGES={"電阻器","電容器","電感器","濾波器、振盪器"}
COMM_PENDING="待核對（官方混合分類）"
COMM_ACTIVE="主動元件（光主動／晶片）"
COMM_PASSIVE="被動元件（電阻電容／濾波等）"
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
   (COMM_ACTIVE,[]),(COMM_PASSIVE,[]),(COMM_PENDING,[]),
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
 {"name":"CPO／矽光子","code":"CPO","keys":[],"groups":[(g,[]) for g in CPO_GROUPS]},
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
            "source":CPO_SOURCE if spec["code"]=="CPO" else SOURCE+"introduce.php?ic="+spec["code"],
            "sourceLabel":"CPO 產業供應鏈研究（非櫃買官方產業碼）" if spec["code"]=="CPO" else "櫃買中心原始產業鏈",
            "subgroups":{}}
    covered=0;upstream_stocks=set();entries_count=0
    published_materials=set();basis_counts={"tpex_official":0,"independent_industry_material":0,"tpex_cross_industry":0,"company_product_verified":0,"tpex_ambiguous":0,"cpo_industry_research":0}
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
        # Separate communications active and passive only with actual product
        # evidence. TPEx I000 parent "主/被動元件" itself is non-discriminating.
        communication=any(normalize(e.get("industry"))=="通信網路"
            and normalize(e.get("subCategory"))=="主被動元件" for e in source)
        j_passive=[e["subCategory"] for e in source if normalize(e.get("industry"))=="被動元件"
            and normalize(e.get("subCategory")) in {normalize(t) for t in COMM_PASSIVE_STAGES}]
        product_groups={}
        if communication:
            if j_passive:
                product_groups[COMM_PASSIVE]={
                    "classification":"通信設備上游：被動元件製造供應商",
                    "basis":"tpex_cross_industry",
                    "source":SOURCE+"company_chain.php?stk_code="+code,
                    "roleNote":"櫃買中心同時列通信網路『主／被動』及被動元件製造段："+
                         "、".join(j_passive)+"。對通信設備是上游供應商，對被動元件產業本身屬中游。"}
            if code in COMM_PASSIVE_EVIDENCE:
                p,u=COMM_PASSIVE_EVIDENCE[code]
                product_groups[COMM_PASSIVE]={"classification":"通信設備上游：被動零組件",
                     "basis":"company_product_verified","source":u,
                     "roleNote":p+"；依公司產品揭露歸類，非官方『主／被動』自動判定。"}
            if code in COMM_ACTIVE_EVIDENCE:
                p,u=COMM_ACTIVE_EVIDENCE[code]
                product_groups[COMM_ACTIVE]={"classification":"通信設備上游：光主動零組件",
                     "basis":"company_product_verified","source":u,
                     "roleNote":p+"；依公司產品／年報揭露歸類。"}
            if not product_groups:
                product_groups[COMM_PENDING]={"classification":"官方通信網路：主／被動未拆分",
                    "basis":"tpex_ambiguous","source":SOURCE+"company_chain.php?stk_code="+code,
                    "roleNote":"公司列入官方通信網路上游混合欄位，但尚未有足夠產品證據區分主動／被動，避免誤判。"}
        # YAGEO is officially TPEx "被動元件" MIDSTREAM even though not registered
        # as an I000 component. For communications end-equipment it is an UPSTREAM
        # supplier. Label this independent cross-chain supplementation explicitly.
        if code=="2327":
            if normalize(x.get("name","")).replace("*","")!="國巨":
                raise RuntimeError("YAGEO 2327 name mismatch")
            if not j_passive:
                raise RuntimeError("YAGEO missing TPEx J000 passive manufacturing chain; refuse inferred inclusion")
            product_groups[COMM_PASSIVE]={"classification":"通信設備上游（跨產業補列）；被動元件產業中游",
                "basis":"tpex_cross_industry","source":SOURCE+"company_chain.php?stk_code=2327",
                "roleNote":"國巨產品含電阻、電容、電感、濾波器。為通信設備上游供應商，但在被動元件產業本身屬中游製造商，不是其材料上游。"}
        for group,meta in product_groups.items():
            matches[("I000",group)]=meta
        if code in WAFER_MATERIALS:
            expected=WAFER_MATERIALS[code]
            if normalize(expected) not in normalize(x.get("name")):
                raise RuntimeError(f"Silicon wafer material code/name conflict for {code}: {x.get('name')!r}")
            matches[("D000","半導體用矽晶圓／磊晶材料（延伸上游）")]={
                "classification":"半導體材料供應鏈（延伸）","basis":"independent_industry_material",
                "source":WAFER_MATERIAL_SOURCE,
                "roleNote":"工研院 ITIS 列為晶圓廠的半導體矽晶圓／磊晶材料供應商；與太陽能矽晶片、晶圓代工製程分層不同。"}
            published_materials.add(code)
        # An independent CPO thematic map (not a TPEx official classification).
        if code in CPO_EVIDENCE:
            group,role,evidence=CPO_EVIDENCE[code]
            matches[("CPO",group)]={
                "classification":"CPO 上游光學零件研究名單（非官方類股）",
                "basis":"cpo_industry_research","source":evidence,
                "roleNote":role+" CPO 技術供應鏈與特定客戶訂單／營收貢獻是兩回事。"}
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
            comm=spec["code"]=="I000" and key in (COMM_ACTIVE,COMM_PASSIVE,COMM_PENDING)
            extended=spec["code"]=="D000" and key.startswith("半導體用矽晶圓")
            solar=spec["code"]=="A100" and key.startswith("太陽能材料")
            cpo=spec["code"]=="CPO"
            note=("另依工研院 ITIS 矽晶圓材料研究補充。此為晶圓廠『材料供應鏈上游』，不同於櫃買中心以 IP／IC 設計為上游的製造流程分層。"
                  if extended else "櫃買中心將太陽能漿料等材料列在此上游；公司可能跨足其他領域，並非太陽能營收比重排名。" if solar else "")
            if comm:
                note=("依公開產品與櫃買中心被動元件產業鏈交叉核對，區分光主動元件及電子被動元件。"
                      "國巨補列為通信設備上游，但屬被動元件產業中游。"
                      if key!=COMM_PENDING else
                      "官方原始『主／被動元件』是合併分類；產品未獲證實者保留待核對，不會猜測。")
            if cpo:note="CPO／矽光子研究補充的光學零件上游；不等於櫃買中心官方產業鏈、CPO 客戶認證、實際訂單或主要營收。"+"此頁不把晶圓代工或交換器系統廠混作元件上游。"
            child.append({"name":key,"count":len(items),"stocks":items,"source":WAFER_MATERIAL_SOURCE if extended else item["source"],"note":note,
                          "classification":"CPO 研究上游" if cpo else "獨立研究延伸上游材料" if extended else "櫃買中心官方上游"})
        item["subgroups"]=child
        item["stockCount"]=len({(z["market"],z["code"]) for g in child for z in g["stocks"]})
        sectors.append(item)
    valid=len([x for x in stocks if x.get("market") in ("上市","上櫃")])
    return {"schema":"tw-upstream-industries-v2","dataDate":data_date,
        "generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "source":"TPEx industry value chains; ITIS semiconductor wafer research; curated CPO optical upstream evidence; dated full-market stock diagnostics",
        "method":"Eight TPEx industry chain upstream classifications, ITIS silicon wafer materials, and a ninth independent CPO optical-components upstream research category (NOT an official TPEx sector nor proof of named customer orders).",
        "coverage":{"marketStocks":valid,"verifiedCompanyPages":covered,"verifiedRatioPct":round(100*covered/valid,1) if valid else 0,
                    "distinctUpstreamStocks":len(upstream_stocks),"upstreamMemberships":entries_count,"industries":len(sectors),
                    "classifiedBySource":basis_counts},
        "audit":{"stageReferences":{i["code"]:SOURCE+"introduce.php?ic="+i["code"] for i in INDUSTRIES if i["code"]!="CPO"},
                 "cpoResearchSource":CPO_SOURCE,
                 "cpoCodes":sorted(CPO_EVIDENCE),
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
    if "CPO" not in {z["code"] for z in result["industries"]}:raise RuntimeError("Missing standalone CPO research classification")
    if "3081" in ids and not any(x["code"]=="3081" for g in next(z for z in result["industries"] if z["code"]=="CPO")["subgroups"] for x in g["stocks"]):
        raise RuntimeError("CPO upstream optical laser supplier 3081 missing")
    if "2327" in ids:
        sector=next(i for i in result["industries"] if i["code"]=="I000")
        passive=next(g for g in sector["subgroups"] if g["name"]==COMM_PASSIVE)
        assert any(z["code"]=="2327" and z["basis"]=="tpex_cross_industry" for z in passive["stocks"]), "YAGEO missing verified communications passive supply"
    if "6488" in ids and "6488" not in result["audit"]["extendedMaterials"]:
        raise RuntimeError("GlobalWafers 6488 MUST appear in semiconductor-grade material suppliers")
    if result["coverage"]["verifiedCompanyPages"]<max(500,int(len(ids)*.5)) or result["coverage"]["distinctUpstreamStocks"]<30:
        raise RuntimeError("Insufficient official company-chain coverage; refuse to publish misleading zero-sector data")
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print("Published",OUT,"date",date,"sectors",{x["name"]:x["stockCount"] for x in result["industries"]},flush=True)
if __name__=="__main__":main()
