/* Self-contained PNG export for the currently displayed G intraday/EOD tables. */
(function(){
"use strict";
function txt(value){return String(value==null?"":value).replace(/\s+/g," ").trim()}
function collect(mode){
 var live=mode==="intraday",table=document.getElementById(live?"stockTable":"officialStockTable");
 if(!table||typeof MODEL!=="string"||MODEL!=="G")throw new Error("請先切換至 G 強勢股選股頁面");
 var snapshot=live?(typeof currentLiveG==="function"?currentLiveG():null):null;
 var source=live?snapshot&&snapshot.asOfDate:DATA&&DATA.dataDate,issued=live?snapshot&&snapshot.publishedAt:DATA&&DATA.generatedAt;
 if(live&&!snapshot)throw new Error("目前沒有可用的當日盤中榜單，請等待資料更新");
 if(!live&&!(DATA&&DATA.gSelection&&DATA.gSelection.dataDate===DATA.dataDate&&Array.isArray(DATA.models&&DATA.models.G)))throw new Error("盤後正式 G 榜單尚未完成，無法下載");
 var header=Array.from(table.tHead&&table.tHead.rows[0]?table.tHead.rows[0].cells:[]).map(function(c){return txt(c.innerText||c.textContent)});
 var all=Array.from(table.tBodies[0]&&table.tBodies[0].rows||[]);
 var rows=all.filter(function(tr){return !tr.classList.contains("simple-detail-row")&&tr.cells.length===header.length&&Array.from(tr.cells).every(function(c){return !c.colSpan||c.colSpan===1})}).map(function(tr){return Array.from(tr.cells).map(function(c){return txt(c.innerText||c.textContent)})});
 if(!header.length||!rows.length)throw new Error("目前篩選結果沒有股票，無法下載空榜單");
 var status=document.getElementById(live?"gIntradayStatus":"gOfficialStatus");
 var warning=live&&typeof gSnapshotNotice==="function"?txt(gSnapshotNotice(snapshot)):"";
 return {mode:mode,date:source,publishedAt:issued,columns:header,rows:rows,status:txt(status&&status.textContent),warning:warning,filtered:typeof THEME_FILTER!=="undefined"?txt(THEME_FILTER):"",compact:table.classList.contains("simple-mode")};
}
function rowWrap(ctx,text,width,maxLines){
 var words=Array.from(txt(text)),lines=[],line="";
 for(var i=0;i<words.length;i++){var next=line+words[i];if(ctx.measureText(next).width>width&&line){lines.push(line);line=words[i]}else line=next;if(lines.length===maxLines)break;}
 if(lines.length<maxLines&&line)lines.push(line);
 if(lines.length===maxLines&&lines.join("").length<words.length){var t=lines[maxLines-1];while(t.length>1&&ctx.measureText(t+"…").width>width)t=t.slice(0,-1);lines[maxLines-1]=t+"…";}
 return lines.length?lines:["—"];
}
function renderPNG(info){
 var cols=info.columns,compact=info.compact;
 if(!cols.length||!info.rows.length)throw new Error("榜單資料不存在");
 var tmp=document.createElement("canvas"),ctx=tmp.getContext("2d");
 if(!ctx)throw new Error("此瀏覽器無法使用圖片繪製功能");
 ctx.font='17px "Microsoft JhengHei","PingFang TC",sans-serif';
 var widths=cols.map(function(head,i){
  if(compact)return [78,325,150,235][i]||160;
  var high=Math.max(ctx.measureText(head).width+30,100),maximum=i===3?340:i===1?245:i===cols.length-1?320:195;
  var peek=info.rows.slice(0,20).reduce(function(v,row){return Math.max(v,Math.min(maximum,ctx.measureText(row[i]||"").width+25))},high);
  return Math.min(maximum,Math.max(i===0?72:100,peek));
 });
 var gap=36,rowHeight=compact?76:70,titleHeight=214,headHeight=52,footHeight=125;
 var width=widths.reduce(function(x,y){return x+y},gap*2),height=titleHeight+headHeight+info.rows.length*rowHeight+footHeight;
 if(width>8500||height>10000)throw new Error("表格過大，無法匯出單張圖片");
 var ratio=Math.min(2,Math.sqrt(18000000/(width*height)));
 var bitmap=document.createElement("canvas");bitmap.width=Math.ceil(width*ratio);bitmap.height=Math.ceil(height*ratio);
 var c=bitmap.getContext("2d");if(!c)throw new Error("建立 PNG 圖片失敗");
 c.scale(ratio,ratio);c.textBaseline="top";c.fillStyle="#fff";c.fillRect(0,0,width,height);
 var ink="#1e293b",accent=info.mode==="intraday"?"#c27625":"#2563eb";
 c.fillStyle=accent;c.fillRect(0,0,width,12);
 c.fillStyle=ink;c.font='bold 34px "Microsoft JhengHei","PingFang TC",sans-serif';c.fillText(info.mode==="intraday"?"G 盤中選股｜暫估榜單":"G 盤後選股｜正式榜單",gap,36);
 c.fillStyle="#475569";c.font='21px "Microsoft JhengHei","PingFang TC",sans-serif';c.fillText("資料日："+info.date+"　│　發布："+txt(info.publishedAt||"未提供"),gap,91);
 c.font='18px "Microsoft JhengHei","PingFang TC",sans-serif';c.fillText("股票數："+info.rows.length+"　│　視圖："+(compact?"簡單模式":"詳細模式")+(info.filtered?"　│　題材篩選："+info.filtered:""),gap,129);
 var notice=info.mode==="intraday"?"未完成日K，屬盤中暫估；非正式進出場訊號。":"已完成日K的正式 G 排行，非當前盤中報價。";
 if(info.warning)notice+="　注意：盤中快照已過期或盤中已結束。";
 c.fillStyle=info.warning?"#b45309":"#64748b";c.font='17px "Microsoft JhengHei","PingFang TC",sans-serif';
 c.fillText(rowWrap(c,notice,width-2*gap,2)[0],gap,164);
 var y=titleHeight;c.fillStyle="#eaf0f8";c.fillRect(gap,y,width-gap*2,headHeight);c.font='bold 18px "Microsoft JhengHei","PingFang TC",sans-serif';c.fillStyle="#334155";
 var x=gap;cols.forEach(function(v,i){c.fillText(rowWrap(c,v,widths[i]-18,1)[0],x+9,y+14);x+=widths[i]});
 info.rows.forEach(function(row,index){
  var top=titleHeight+headHeight+index*rowHeight;c.fillStyle=index%2===0?"#ffffff":"#f8fbff";c.fillRect(gap,top,width-2*gap,rowHeight);
  c.strokeStyle="#e5ebf2";c.beginPath();c.moveTo(gap,top+rowHeight-.5);c.lineTo(width-gap,top+rowHeight-.5);c.stroke();
  c.font=(index===0?"bold ":"")+'17px "Microsoft JhengHei","PingFang TC",sans-serif';c.fillStyle=ink;x=gap;
  row.forEach(function(v,i){if(i>=widths.length)return;var lines=rowWrap(c,v,widths[i]-18,2),lh=23,sy=top+(rowHeight-lines.length*lh)/2;
   lines.forEach(function(line,j){c.fillText(line,x+9,sy+j*lh)});x+=widths[i];});
 });
 y=titleHeight+headHeight+info.rows.length*rowHeight;c.fillStyle="#64748b";c.font='17px "Microsoft JhengHei","PingFang TC",sans-serif';
 c.fillText("來源：Tradingview-testing / G 選股儀表板",gap,y+22);
 c.fillText("匯出時間："+new Date().toLocaleString("zh-TW",{timeZone:"Asia/Taipei",hour12:false})+"（台灣）",gap,y+51);
 c.font='16px "Microsoft JhengHei","PingFang TC",sans-serif';c.fillText("僅供研究與交易輔助；請以原始資料與實際成交價核對。",gap,y+80);
 return bitmap;
}
function download(mode,button){
 var prev=button.textContent;button.disabled=true;button.textContent="圖片製作中…";
 try{var info=collect(mode),canvas=renderPNG(info),name="G_"+(mode==="intraday"?"盤中暫估":"盤後正式")+"_"+txt(info.date).replace(/[^0-9-]/g,"")+(mode==="intraday"?"_"+txt(info.publishedAt).slice(11,16).replace(":",""):"")+".png";
  canvas.toBlob(function(blob){if(!blob){alert("圖片轉換失敗，請嘗試簡單模式");button.disabled=false;button.textContent=prev;return}
   var url=URL.createObjectURL(blob),link=document.createElement("a");link.href=url;link.download=name;document.body.appendChild(link);link.click();link.remove();setTimeout(function(){URL.revokeObjectURL(url)},30000);
   button.disabled=false;button.textContent=prev;
  },"image/png");
 }catch(e){button.disabled=false;button.textContent=prev;alert("無法下載榜單圖片："+e.message)}
}
[["gExportIntraday","intraday"],["gExportOfficial","official"]].forEach(function(pair){var b=document.getElementById(pair[0]);if(b)b.addEventListener("click",function(){download(pair[1],b)})});
window.GRankImageExport={collect:collect,renderPNG:renderPNG};
})();
