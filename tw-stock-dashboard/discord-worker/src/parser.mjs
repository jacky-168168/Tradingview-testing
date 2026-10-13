/** Parse existing Alert bot text; do not invent Trend or timeframe. */
export function parseDiscordMessage(message, channel) {
  if (!message || !/^\d+$/.test(String(message.id ?? ""))) return [];
  const time = Date.parse(String(message.timestamp || ""));
  if (!Number.isFinite(time)) return [];
  const sources = [message.content || ""];
  for (const embed of message.embeds || []) {
    if (embed?.title) sources.push(embed.title);
    if (embed?.description) sources.push(embed.description);
    for (const field of embed.fields || []) sources.push(String(field.name || "") + "\n" + String(field.value || ""));
  }
  const fulltext = sources.join("\n").replace(/\r/g, "");
  const re = /^\s*(\d{4,6}[A-Z]?)\s+(?:(SS)\s+)?(bottom|top)\s+alert\s+triggered\s*,?\s*price\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*$/gim;
  const out = [], duplicates = new Set();
  let match;
  while ((match = re.exec(fulltext)) !== null) {
    const symbol=match[1].toUpperCase(), variant=match[2] ? "SS" : "NORMAL", signal=match[3].toUpperCase(), price=Number(match[4]);
    if (!(price>0 && price<10000000)) continue;
    const key=[symbol,variant,signal,price].join(":");
    if (duplicates.has(key)) continue;
    duplicates.add(key);
    out.push({
      id:String(channel.id)+":"+String(message.id)+":"+out.length,
      discord_message_id:String(message.id),channel_id:String(channel.id),
      source:String(channel.name),timeframe:channel.timeframe || null,
      symbol,signal,variant,price,time
    });
  }
  return out;
}
export const DEFAULT_CHANNELS = [
  {id:"1540171776418390038",name:"day-trading",timeframe:null},
  {id:"1541319920007254066",name:"5-min小波段通知",timeframe:"5"}
];
export function configuredChannels(raw) {
  if (!raw) return DEFAULT_CHANNELS;
  const channels=JSON.parse(raw);
  if (!Array.isArray(channels) || channels.length<1 || channels.length>10) throw Error("CHANNELS_CONFIG must contain 1-10 channels");
  const seen=new Set();
  return channels.map(x=>{
    if(!/^\d{15,22}$/.test(String(x.id||"")))throw Error("Invalid channel ID");
    if(seen.has(String(x.id)))throw Error("Duplicate channel ID");
    seen.add(String(x.id));
    const tf = x.timeframe == null || x.timeframe === "unknown" ? null : String(x.timeframe);
    if(tf !== null && !["2","5","15","D"].includes(tf))throw Error("Invalid declared timeframe");
    return {id:String(x.id),name:String(x.name||x.id).slice(0,64),timeframe:tf};
  });
}
