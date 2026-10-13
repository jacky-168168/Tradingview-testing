import {parseDiscordMessage,configuredChannels} from "./parser.mjs";
const DISCORD_BASE="https://discord.com/api/v10";
function cors(request, env) {
  const origin=request.headers.get("Origin"), expected=String(env.ALLOWED_ORIGIN || "");
  if(origin && origin!==expected)return null;
  return {"Access-Control-Allow-Origin":expected,"Access-Control-Allow-Methods":"GET, OPTIONS","Access-Control-Allow-Headers":"Authorization, Content-Type","Vary":"Origin","Cache-Control":"no-store"};
}
function json(data,status=200,headers={}) {return new Response(JSON.stringify(data),{status,headers:{"Content-Type":"application/json;charset=UTF-8","Cache-Control":"no-store",...headers}});}
async function constantTimeEqual(a,b){
  if(!a||!b)return false;
  const enc=new TextEncoder();
  const [ha,hb]=await Promise.all([crypto.subtle.digest("SHA-256",enc.encode(a)),crypto.subtle.digest("SHA-256",enc.encode(b))]);
  const va=new Uint8Array(ha),vb=new Uint8Array(hb);let diff=0;
  for(let i=0;i<va.length;i++)diff |= va[i]^vb[i];
  return diff===0;
}
function validSnowflake(s){return /^\d{15,22}$/.test(String(s||""))}
async function readDiscordPage(env,channel,before,fetchImpl=fetch){
  if(!env.DISCORD_BOT_TOKEN)throw Error("Missing DISCORD_BOT_TOKEN secret");
  const url=new URL(DISCORD_BASE+"/channels/"+channel.id+"/messages");
  url.searchParams.set("limit","100");
  if(before)url.searchParams.set("before",before);
  const response=await fetchImpl(url.toString(),{headers:{"Authorization":"Bot "+env.DISCORD_BOT_TOKEN,"User-Agent":"TWStockSignalReceiver (owner-configured)","Accept":"application/json"}});
  if(response.status===429){
    const seconds=response.headers.get("Retry-After")||"unknown";
    throw Error("Discord rate limited (429), retry after "+seconds+" seconds");
  }
  if(!response.ok)throw Error("Discord messages API HTTP "+response.status+" for "+channel.name);
  const data=await response.json();
  if(!Array.isArray(data))throw Error("Discord API returned invalid messages");
  return data;
}
async function recordFailure(env,ch,error){
  const text=String(error.message||error).slice(0,350);
  await env.DB.prepare("INSERT INTO discord_cursor(channel_id,last_message_id,last_checked_ms,last_error,last_inserted) VALUES(?,'0',?,?,0) ON CONFLICT(channel_id) DO UPDATE SET last_checked_ms=excluded.last_checked_ms,last_error=excluded.last_error,last_inserted=0").bind(ch.id,Date.now(),text).run();
}
export async function pollOne(env,ch,fetchImpl=fetch){
  if(!validSnowflake(ch.id))throw Error("Invalid Discord channel ID");
  const state=await env.DB.prepare("SELECT last_message_id FROM discord_cursor WHERE channel_id=?").bind(ch.id).first();
  const cursor=state?.last_message_id || "0";
  if(!validSnowflake(cursor)&&cursor!=="0")throw Error("Invalid stored Discord cursor");
  let older=null,all=[],covered=false,maxSeen=cursor;
  // From latest to oldest. We do not advance the cursor when we cannot cover a full backlog.
  for(let page=0;page<15;page++){
    const batch=await readDiscordPage(env,ch,older,fetchImpl);
    if(!batch.length){covered=true;break}
    const valid=batch.filter(m=>validSnowflake(m.id));
    if(!valid.length)throw Error("Discord returned invalid message identifiers");
    for(const m of valid){
      if(BigInt(m.id)>BigInt(maxSeen))maxSeen=String(m.id);
      if(BigInt(m.id)>BigInt(cursor))all.push(m);
    }
    const oldest=valid.reduce((min,m)=>BigInt(m.id)<BigInt(min)?m.id:min,valid[0].id);
    if(cursor==="0"||BigInt(oldest)<=BigInt(cursor)||batch.length<100){covered=true;break}
    if(older!==null && BigInt(oldest)>=BigInt(older))throw Error("Discord pagination did not progress");
    older=String(oldest);
  }
  if(!covered)throw Error("Discord backlog exceeds 1500 messages; cursor not advanced");
  all.sort((a,b)=>BigInt(a.id)<BigInt(b.id)?-1:BigInt(a.id)>BigInt(b.id)?1:0);
  const allowedAuthors=new Set(String(env.ALLOWED_AUTHOR_IDS||"").split(",").map(x=>x.trim()).filter(Boolean));
  const inserts=[];
  for(const msg of all){
    if(allowedAuthors.size&&!allowedAuthors.has(String(msg.author?.id||"")))continue;
    for(const s of parseDiscordMessage(msg,ch)){
      inserts.push(env.DB.prepare("INSERT OR IGNORE INTO discord_signals(id,discord_message_id,channel_id,source,symbol,signal,variant,trend_gt_70,price,timeframe,time_ms) VALUES(?,?,?,?,?,?,?,?,?,?,?)").bind(s.id,s.discord_message_id,s.channel_id,s.source,s.symbol,s.signal,s.variant,s.trend_gt_70?1:0,s.price,s.timeframe,s.time));
    }
  }
  // Partial successful batches are safe to retry because of the unique signal ID.
  for(let i=0;i<inserts.length;i+=45)await env.DB.batch(inserts.slice(i,i+45));
  await env.DB.prepare("INSERT INTO discord_cursor(channel_id,last_message_id,last_checked_ms,last_error,last_inserted) VALUES(?,?,?,?,?) ON CONFLICT(channel_id) DO UPDATE SET last_message_id=excluded.last_message_id,last_checked_ms=excluded.last_checked_ms,last_error='',last_inserted=excluded.last_inserted").bind(ch.id,maxSeen,Date.now(),"",inserts.length).run();
  return {channel:ch.name,messages:all.length,signals:inserts.length,cursor:maxSeen};
}
export async function pollAll(env,fetchImpl=fetch){
  const channels=configuredChannels(env.CHANNELS_CONFIG);const results=[];
  for(const ch of channels){
    try{results.push(await pollOne(env,ch,fetchImpl))}
    catch(err){
      results.push({channel:ch.name,error:String(err.message||err)});
      try{await recordFailure(env,ch,err)}catch(e){console.error("Could not record poll error for "+ch.name)}
    }
  }
  console.log("Discord poll summary",JSON.stringify(results));
  return results;
}
async function auth(request,secret) {
  const h=request.headers.get("Authorization")||"";
  return h.startsWith("Bearer ")&&await constantTimeEqual(h.slice(7),secret);
}
function readChannelMap(env){
  const m=new Map();for(const ch of configuredChannels(env.CHANNELS_CONFIG))m.set(ch.id,ch);
  return m;
}
const app={
 async fetch(request,env){
  const url=new URL(request.url),headers=cors(request,env);
  if(headers===null)return json({error:"Origin not allowed"},403);
  if(request.method==="OPTIONS"&&url.pathname.startsWith("/api/"))return new Response(null,{status:204,headers});
  if(!env.DB)return json({error:"D1 database is not configured"},503,headers);
  if(!env.DASHBOARD_READ_TOKEN || !env.DISCORD_BOT_TOKEN)return json({error:"Required Worker secrets are not configured"},503,headers);
  if(url.pathname==="/api/events" && request.method==="GET"){
    if(!await auth(request,env.DASHBOARD_READ_TOKEN))return json({error:"Unauthorized"},401,headers);
    const lim=Math.max(1,Math.min(500,Math.floor(Number(url.searchParams.get("limit"))||100)));
    const sinceRaw=Number(url.searchParams.get("since")),since=sinceRaw>0?Math.min(Date.now(),Math.max(Date.now()-90*86400000,sinceRaw)):Date.now()-7*86400000;
    const {results}=await env.DB.prepare("SELECT id,channel_id,source,symbol,signal,variant,trend_gt_70,price,timeframe,time_ms FROM discord_signals WHERE time_ms>=? ORDER BY time_ms DESC, id DESC LIMIT ?").bind(since,lim).all();
    const chan=readChannelMap(env);
    const events=(results||[]).map(r=>({id:r.id,channel:r.source,channelId:r.channel_id,symbol:r.symbol,signal:r.signal,variant:r.variant,trendGt70: r.trend_gt_70===1,price:r.price,time:r.time_ms,trend:null,g:null,timeframe:chan.has(r.channel_id)?chan.get(r.channel_id).timeframe:r.timeframe}));
    return json({asOf:Date.now(),count:events.length,events},200,headers);
  }
  if(url.pathname==="/api/status" && request.method==="GET"){
    if(!await auth(request,env.DASHBOARD_READ_TOKEN))return json({error:"Unauthorized"},401,headers);
    const {results}=await env.DB.prepare("SELECT channel_id,last_message_id,last_checked_ms,last_error,last_inserted FROM discord_cursor").all();
    const state=new Map((results||[]).map(r=>[r.channel_id,r]));
    return json({asOf:Date.now(),channels:configuredChannels(env.CHANNELS_CONFIG).map(c=>({name:c.name,id:c.id,timeframe:c.timeframe,lastChecked:state.get(c.id)?.last_checked_ms||null,lastError:state.get(c.id)?.last_error||null,lastSignals:state.get(c.id)?.last_inserted||0}))},200,headers);
  }
  if(url.pathname==="/api/sync" && request.method==="POST"){
    if(!env.SYNC_TOKEN||!await auth(request,env.SYNC_TOKEN))return json({error:"Unauthorized"},401,headers);
    return json({results:await pollAll(env)},200,headers);
  }
  return json({error:"Not found"},404,headers);
 },
 async scheduled(controller,env,ctx){ctx.waitUntil(pollAll(env));}
};
export default app;
