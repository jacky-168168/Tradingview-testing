"""Discover TAIFEX's official annual daytime/after-hours CSV ZIP downloads.
Read-only probe. No archive rewriting. Not used to create fabricated backtest results."""
import re,json,requests
from bs4 import BeautifulSoup
U="https://www.taifex.com.tw/cht/3/futDailyMarketView"
def main():
    resp=requests.get(U,timeout=30,headers={"User-Agent":"Mozilla/5.0"})
    print("HTTP",resp.status_code,"FINAL",resp.url,"BYTES",len(resp.content));resp.raise_for_status()
    soup=BeautifulSoup(resp.content,"html.parser")
    for form in soup.select("form"):
        controls=[{"tag":t.name,"name":t.get("name"),"id":t.get("id"),"value":t.get("value"),"text":t.get_text(" ",strip=True)[:120]} for t in form.find_all(["input","select","button"],recursive=True)]
        print("FORM",json.dumps({"id":form.get("id"),"method":form.get("method"),"action":form.get("action"),"controls":controls[:60]},ensure_ascii=False))
    for a in soup.select("a[href]"):
        url=a.get("href","");label=a.get_text(" ",strip=True)
        if re.search("year|zip|futdaily|download|歷史|年度|年度行情|下載",url+" "+label,re.I):
            print("LINK",repr(url[:300]),repr(label[:100]))
    for key in ['id="hisForm"','name="his_year"','futDataDown','down_type','hisForm.submit']:
        off=resp.text.find(key)
        if off>=0:print("ANNUAL_SNIPPET",key,resp.text[max(0,off-600):off+1700].replace("\\n"," ")[:2200])
    for line in resp.text.splitlines():
        if re.search(r"year|zip|annual|futdaily|download",line,re.I) and re.search(r"action|onclick|\.zip|function |fetch|href=|submit|\.do|\.ashx|url=",line,re.I):
            print("JS_HINT",line.strip()[:500])
if __name__=="__main__":main()
