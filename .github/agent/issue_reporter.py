"""Deduplicated AI harness health alerts. No notifications for off-hours G."""
from __future__ import annotations
import hashlib,json,os,sys
from urllib.request import Request,urlopen
from health import API
PREFIX="[LOOP-HEALTH] "
TRACKS={"g":"G 盤中服務","news":"重大新聞服務"}
def request(path,method="GET",data=None):
    headers={"Authorization":"Bearer "+os.environ["GITHUB_TOKEN"],"Accept":"application/vnd.github+json",
             "User-Agent":"tw-loop-health","X-GitHub-Api-Version":"2022-11-28"}
    raw=json.dumps(data,ensure_ascii=False).encode("utf-8") if data is not None else None
    if raw:headers["Content-Type"]="application/json"
    with urlopen(Request(API+path,data=raw,headers=headers,method=method),timeout=20) as r:
        x=r.read().decode("utf-8");return json.loads(x) if x else None
def track_of(kind):
    return "news" if kind.startswith("news") else "g"
def fingerprint(items):
    # Deliberately exclude changing elapsed minutes, avoiding repeated noise.
    return hashlib.sha256(json.dumps(sorted((x["kind"],x["detail"]) for x in items),ensure_ascii=False).encode()).hexdigest()[:16]
def issue_body(track,result,rows,fp):
    reference=("https://github.com/jacky-168168/Tradingview-testing/actions\n"
       "https://raw.githubusercontent.com/jacky-168168/Tradingview-testing/main/tw-stock-dashboard/docs/data/g_intraday/latest.json\n"
       "https://jacky-168168.github.io/Tradingview-testing/market-events.html")
    lines=[f"**診斷時間（臺灣）：** {result['checkedAt']}",f"**類別：** {TRACKS[track]}"]
    if track=="g":
        lines += [f"**最後成功榜單：** {result.get('gLastPublishedAt')}",
                  f"**有效報價：** {json.dumps(result.get('gCoverage'),ensure_ascii=False)[:350]}"]
    else:
        lines += [f"**新聞資料時間：** {result.get('newsGeneratedAt')}",
                  f"**最新文章：** {result.get('newsNewestAt')}"]
    lines += ["**異常：**"]+[f"- [{x['kind']}] {x['detail']}"+(f"（{x.get('ageMinutes')} 分鐘）" if "ageMinutes" in x else "") for x in rows]
    lines += ["**查核連結：**",reference,"僅建立巡檢紀錄，不代表根因已確認或程式已修復。",
               f"<!-- loop-health:{track}:{fp} -->"]
    return "\n\n".join(lines)
def reconcile(result,api=request):
    scope=set(result.get("scopes",[]))
    issues=api("/issues?state=all&sort=updated&direction=desc&per_page=100")
    for track,title in TRACKS.items():
        if track not in scope:continue
        rows=[x for x in result.get("incidents",[]) if track_of(x["kind"])==track]
        issue=next((x for x in issues if x.get("title")==PREFIX+title and not x.get("pull_request")),None)
        if not rows:
            if issue and issue.get("state")=="open":
                api(f"/issues/{issue['number']}/comments","POST",{"body":"✅ 已於 "+result["checkedAt"]+" 通過固定驗收；僅表示此時復原，非根因已排除。"})
                api(f"/issues/{issue['number']}","PATCH",{"state":"closed","state_reason":"completed"})
            continue
        fp=fingerprint(rows)
        if issue and issue.get("state")=="open" and f"<!-- loop-health:{track}:{fp} -->" in (issue.get("body") or ""):
            print("HEALTH_REPEAT_SUPPRESSED",track,fp);continue
        body=issue_body(track,result,rows,fp)
        if issue:
            api(f"/issues/{issue['number']}","PATCH",{"state":"open","body":body})
        else:
            api("/issues","POST",{"title":PREFIX+title,"body":body,"assignees":["jacky-168168"]})
        print("HEALTH_NEW_OR_CHANGED",track,fp)
if __name__=="__main__":
    with open(sys.argv[1] if len(sys.argv)>1 else "agent-health.json",encoding="utf-8") as f:reconcile(json.load(f))
