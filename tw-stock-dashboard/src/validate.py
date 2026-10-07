from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np

def load(p):return json.loads(Path(p).read_text(encoding="utf-8"))
def models(d):
    m=d.get("models") or {}
    if isinstance(m,dict):return m
    return {str(x.get("id")):x.get("rows") or x.get("ranking") or x.get("top20") or [] for x in m if x.get("id")}

def codes(rows,n=20):return [str(x.get("code")) for x in (rows or [])[:n] if x.get("code")]
def scores(rows):return {str(x.get("code")):float(x.get("total") or x.get("score") or 0) for x in rows or [] if x.get("code")}

def compare(py,gas):
    pm,gm=models(py),models(gas);out={"models":{}}
    for mid in ["A","D"]:
        pc,gc=codes(pm.get(mid,[])),codes(gm.get(mid,[]));inter=[x for x in pc if x in set(gc)];same=sum(1 for i,x in enumerate(pc) if i<len(gc) and x==gc[i]);ps,gs=scores(pm.get(mid,[])),scores(gm.get(mid,[]));common=set(ps)&set(gs)
        out["models"][mid]={"pythonTop20":pc,"gasTop20":gc,"overlap":len(inter),"overlapPct":round(len(inter)/max(1,min(20,len(gc),len(pc)))*100,1),"sameRank":same,"scoreMad":round(float(np.mean([abs(ps[k]-gs[k]) for k in common])),3) if common else None}
    pr=py.get("risk") or {};gr=gas.get("risk") or gas.get("marketRisk") or {}
    out["risk"]={"pythonScore":pr.get("score"),"gasScore":gr.get("score"),"delta":round(abs(float(pr.get("score",0))-float(gr.get("score",0))),2) if pr.get("score") is not None and gr.get("score") is not None else None}
    out["passSuggested"]=all(out["models"][m]["overlap"]>=16 for m in ["A","D"])
    return out

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--python",dest="py",required=True);ap.add_argument("--gas",required=True);ap.add_argument("--out");a=ap.parse_args();r=compare(load(a.py),load(a.gas));s=json.dumps(r,ensure_ascii=False,indent=2);print(s)
    if a.out:Path(a.out).write_text(s,encoding="utf-8")
