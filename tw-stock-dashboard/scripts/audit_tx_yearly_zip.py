"""Read-only official annual archive probe; no unverified trading claims."""
import requests,io,zipfile
u="https://www.taifex.com.tw/cht/3/futDataDown"
def main():
    print("OFFICIAL_URL",u,flush=True)
    r=requests.post(u,data={"down_type":"2","his_year":"2025"},timeout=110,headers={"User-Agent":"Mozilla/5.0","Referer":"https://www.taifex.com.tw/cht/3/futDailyMarketView"})
    print("OFFICIAL_STATUS",r.status_code,"TYPE",r.headers.get("Content-Type"),"SIZE",len(r.content),"START",repr(r.content[:18]),flush=True)
    r.raise_for_status()
    if not zipfile.is_zipfile(io.BytesIO(r.content)):
        print("OFFICIAL_NOT_ZIP",r.text[:500],flush=True);return
    with zipfile.ZipFile(io.BytesIO(r.content)) as f:
        names=f.namelist()
        print("OFFICIAL_ARCHIVE_ENTRIES",len(names),"NAMES",names[:35],flush=True)
        for name in names[:3]:
            if name.endswith("/"):continue
            print("OFFICIAL_MEMBER",name,"BYTES",f.getinfo(name).file_size,flush=True)
            first=f.open(name).read(1300)
            for enc in ("utf-8-sig","big5","cp950","latin1"):
                try:
                    x=first.decode(enc)
                    print("OFFICIAL_SAMPLE",enc,repr(x[:1000]),flush=True)
                    break
                except UnicodeDecodeError:continue
if __name__=="__main__":main()
