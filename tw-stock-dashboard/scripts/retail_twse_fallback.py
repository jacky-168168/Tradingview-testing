"""TWSE 公開資料推估上市融資維持率；對於日期或涵蓋率不明的資料一律拒絕。
上市（TWSE）= Σ(融資餘額張數 × 1000 × 收盤價) / 全市場融資金額餘額 × 100。
只計算上市，並不冒稱上市櫃整體或券商整戶維持率。
"""
from __future__ import annotations
import re, math, requests
from datetime import datetime
from zoneinfo import ZoneInfo
HEAD={"User-Agent":"Mozilla/5.0 (compatible; Taiwan Stock Dashboard/1.0)"}
URLS={
"margin":"https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN",
"close":"https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
"loan":"https://www.twse.com.tw/exchangeReport/MI_MARGN",
"index":"https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK",
}
def get(url,params=None):
 r=requests.get(url,params=params,headers=HEAD,timeout=28)
 r.raise_for_status()
 return r.json()
def value(x):
 try:
  v=float(str(x).replace(",","").strip())
  return v if math.isfinite(v) else None
 except (ValueError,TypeError):return None
def date_of(raw):
 text=str(raw or "")
 m=re.search(r"(\d{3,4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",text)
 if not m:m=re.search(r"(?<!\d)(\d{3,4})[/-](\d{1,2})[/-](\d{1,2})(?!\d)",text)
 if m:
  y=int(m[1]);return f"{y+(1911 if y<1911 else 0):04d}-{int(m[2]):02d}-{int(m[3]):02d}"
 m=re.search(r"(20\d{2})(\d\d)(\d\d)",text)
 if m:return f"{m[1]}-{m[2]}-{m[3]}"
 m=re.search(r"(?<!\d)(\d{3})(\d\d)(\d\d)(?!\d)",text)
 if m:return f"{int(m[1])+1911:04d}-{m[2]}-{m[3]}"
 return None
def main():
 summary=get(URLS["loan"],{"response":"json","selectType":"MS"})
 if summary.get("stat")!="OK":raise RuntimeError("TWSE 融資金額報表非 OK")
 day=date_of(summary.get("date")) or date_of(summary.get("title"))
 if not day:
  for tab in summary.get("tables") or []:
   day=date_of(tab.get("title"))
   if day:break
 if not day:raise RuntimeError("TWSE 金額報表缺少可核對的日期")
 if day>datetime.now(ZoneInfo("Asia/Taipei")).date().isoformat():
  raise RuntimeError("TWSE 交易日期在未來")
 loan=None
 for tab in summary.get("tables") or []:
  cols=[str(x).strip() for x in tab.get("fields") or []]
  if "今日餘額" not in cols:continue
  pos=cols.index("今日餘額")
  for row in tab.get("data") or []:
   if row and "融資金額" in str(row[0]) and "仟元" in str(row[0]) and len(row)>pos:
    v=value(row[pos])
    if v and v>10_000_000:loan=v*1000
 if not loan:raise RuntimeError("TWSE 融資總借款金額缺失")
 margin=get(URLS["margin"])
 quote=get(URLS["close"])
 if not isinstance(margin,list) or not isinstance(quote,list):
  raise RuntimeError("TWSE 個股行情或融資餘額格式錯誤")
 balances={}
 for row in margin:
  if not isinstance(row,dict):continue
  code=str(row.get("股票代號") or "").strip()
  lots=value(row.get("融資今日餘額"))
  if code and lots is not None and lots>=0:balances[code]=lots
 closes={}
 for row in quote:
  if not isinstance(row,dict):continue
  code=str(row.get("Code") or "").strip()
  close=value(row.get("ClosingPrice"))
  if code and close and close>0:closes[code]=close
 positive={k:v for k,v in balances.items() if v>0}
 matched={k:v for k,v in positive.items() if k in closes}
 coverage=len(matched)/len(positive) if positive else 0
 if len(matched)<500 or coverage<.75:
  raise RuntimeError(f"上市報價涵蓋不足：{len(matched)}/{len(positive)} ({coverage:.1%})")
 collateral=sum(lots*1000*closes[code] for code,lots in matched.items())
 ratio=round(collateral/loan*100,2)
 if not 95<ratio<350:raise RuntimeError(f"上市維持率不合理：{ratio}")
 # 指數月報：驗證當日加權收盤，不使用當日日期冒充「報表日期」。
 idx=get(URLS["index"],{"response":"json","date":day.replace("-","")})
 if idx.get("stat")!="OK":raise RuntimeError("TWSE FMTQIK 指數月報非 OK")
 indexes={}
 for tab in [idx]+list(idx.get("tables") or []):
  cols=tab.get("fields") or []
  candidates=[i for i,x in enumerate(cols) if "發行量加權股價指數" in str(x)]
  for row in tab.get("data") or []:
   if not isinstance(row,list) or not row or not candidates:continue
   d=date_of(row[0])
   if d and len(row)>candidates[0]:
    close=value(row[candidates[0]])
    if close and 3000<close<100000:indexes[d]=close
 if day not in indexes:raise RuntimeError("TWSE FMTQIK 未核對到與融資報表相同交易日的指數")
 print("TWSE_DERIVED",day,"listed",ratio,"match",len(matched),"coverage",round(coverage,4),"index",indexes[day])
 return {"date":day,"listed":ratio,"otc":None,"overall":None,"indexClose":round(indexes[day],2),
         "provenance":"TWSE 公開日資料自行計算，僅上市"}
if __name__=="__main__":
 print(main())
