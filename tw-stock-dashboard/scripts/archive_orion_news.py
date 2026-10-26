#!/usr/bin/env python3
"""Publish ORION daily research record and 30-day index after Gemini classifier run."""
from __future__ import annotations
import datetime as dt
import importlib.util
from pathlib import Path
MODULE=Path(__file__).with_name("collect_orion_news.py")
spec=importlib.util.spec_from_file_location("orion_collector",MODULE)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
def run(now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    report=mod.read(mod.OUT,{})
    stamp=mod.parse_date(report.get("generatedAt"))
    if report.get("schema")!=1 or stamp is None or not -60<=(now-stamp).total_seconds()<=3600:
        raise ValueError("ORION: no valid recent collection to archive")
    path=mod.ARCHIVE/(now.astimezone(mod.TPE).date().isoformat()+".json")
    old=mod.read(path,{})
    snapshot=mod.archive(report,now=now,old=old)
    mod.write(path,snapshot)
    mod.save_index(report,snapshot,now)
    print("ORION_HISTORY_ARCHIVED",len(snapshot["items"]),snapshot["day"])
if __name__=="__main__":run()
