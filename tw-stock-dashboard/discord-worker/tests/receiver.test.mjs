import test from "node:test";
import assert from "node:assert/strict";
import {parseDiscordMessage,configuredChannels,DEFAULT_CHANNELS} from "../src/parser.mjs";
import worker,{pollOne,pollAll} from "../src/index.mjs";

const channel=DEFAULT_CHANNELS[0];
const message=(id,content)=>({id:String(id),content,timestamp:"2026-10-13T09:52:00+08:00",embeds:[]});
class MemoryDB {
 constructor(){this.cursor=new Map();this.signals=new Map();this.errors=[];}
 prepare(query){
  const db=this;
  return {bind(...args){
   return {
    async first(){return query.startsWith("SELECT last_message_id")?db.cursor.has(args[0])?{last_message_id:db.cursor.get(args[0]).last_message_id}:null:null},
    async run(){
     if(query.startsWith("INSERT OR IGNORE INTO discord_signals"))db.signals.set(args[0],args);
     if(query.startsWith("INSERT INTO discord_cursor")){
      const id=args[0],previous=db.cursor.get(id)||{last_message_id:"0"};
      if(query.includes("DO UPDATE SET last_checked_ms"))db.cursor.set(id,{...previous,last_error:args[2]});
      else db.cursor.set(id,{last_message_id:args[1],last_error:args[3],last_inserted:args[4]});
     }
     return {success:true};
    },
    async all(){
     if(query.includes("FROM discord_signals"))return {results:[...db.signals].map(([id,a])=>({id,channel_id:a[2],source:a[3],symbol:a[4],signal:a[5],variant:a[6],price:a[7],timeframe:a[8],time_ms:a[9]}))};
     if(query.includes("FROM discord_cursor"))return {results:[...db.cursor].map(([channel_id,s])=>({channel_id,...s}))};
     return {results:[]};
    }
   }
  }};
 }
 async batch(statements){for(const stmt of statements)await stmt.run();return statements.map(()=>({success:true}))}
}
function mockFetch(messages,status=200){
 return async (url,opts)=>({
  status,ok:status===200,
  headers:{get:()=>null},
  json:async()=>messages
 });
}
test("normal and SS duplicates remain different records for UI grouping",()=>{
 const signals=parseDiscordMessage(message("1559418059410907999","8039 SS bottom alert triggered, price: 272.0\n8039 bottom alert triggered, price: 272.0\n2464 top alert triggered, price: 190.5"),channel);
 assert.equal(signals.length,3);
 assert.deepEqual(signals.map(x=>x.variant),["SS","NORMAL","NORMAL"]);
 assert.deepEqual(signals.map(x=>x.signal),["BOTTOM","BOTTOM","TOP"]);
 assert.equal(signals[0].timeframe,null);
});
test("parse embedded messages and suppress duplicate text+embed rows",()=>{
 const m=message("1559418059410907999","2492 SS bottom alert triggered, price: 382.5");
 m.embeds=[{description:m.content}];
 assert.equal(parseDiscordMessage(m,channel).length,1);
});
test("unrelated Discord chat is ignored",()=>{
 assert.deepEqual(parseDiscordMessage(message("1559418059410907999","Hello, 2492 is 382.5"),channel),[]);
});
test("default source timeframes are conservative",()=>{
 assert.equal(DEFAULT_CHANNELS[0].timeframe,null);
 assert.equal(DEFAULT_CHANNELS[1].timeframe,"5");
 assert.throws(()=>configuredChannels('[{"id":"bad","name":"X","timeframe":"2"}]'));
});
test("poll keeps durable cursor, stores signals and replays idempotently",async()=>{
 const db=new MemoryDB(),env={DB:db,DISCORD_BOT_TOKEN:"local-test-token"};
 const rows=[message("1559418059410907999","8039 SS bottom alert triggered, price: 272.0"),message("1559418059410907000","2464 bottom alert triggered, price: 184.5")];
 const r=await pollOne(env,channel,mockFetch(rows));
 assert.equal(r.signals,2);
 assert.equal(db.signals.size,2);
 assert.equal(db.cursor.get(channel.id).last_message_id,"1559418059410907999");
 await pollOne(env,channel,mockFetch(rows));
 assert.equal(db.signals.size,2);
});
test("Discord API error does not advance cursor",async()=>{
 const db=new MemoryDB(),env={DB:db,DISCORD_BOT_TOKEN:"local-test-token"};
 await assert.rejects(()=>pollOne(env,channel,mockFetch([],403)),/HTTP 403/);
 assert.equal(db.cursor.size,0);
});
test("pollAll records errors per channel",async()=>{
 const db=new MemoryDB(),env={DB:db,DISCORD_BOT_TOKEN:"local-test-token",CHANNELS_CONFIG:JSON.stringify([channel])};
 const r=await pollAll(env,mockFetch([],429));
 assert.equal(r[0].channel,"day-trading");
 assert.match(db.cursor.get(channel.id).last_error,/rate limited/);
});
test("events endpoint requires Bearer token and approved CORS origin",async()=>{
 const db=new MemoryDB(),env={DB:db,DISCORD_BOT_TOKEN:"local-test-token",DASHBOARD_READ_TOKEN:"a-long-private-read-secret",ALLOWED_ORIGIN:"https://jacky-168168.github.io"};
 const blocked=await worker.fetch(new Request("https://receiver.example/api/events",{headers:{Origin:"https://other.example"}}),env);
 assert.equal(blocked.status,403);
 const unauthorized=await worker.fetch(new Request("https://receiver.example/api/events",{headers:{Origin:"https://jacky-168168.github.io"}}),env);
 assert.equal(unauthorized.status,401);
 const allowed=await worker.fetch(new Request("https://receiver.example/api/events",{headers:{Origin:"https://jacky-168168.github.io",Authorization:"Bearer a-long-private-read-secret"}}),env);
 assert.equal(allowed.status,200);
 assert.equal((await allowed.json()).count,0);
});
