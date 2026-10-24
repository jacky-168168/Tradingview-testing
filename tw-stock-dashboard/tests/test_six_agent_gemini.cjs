"use strict";
const assert=require("node:assert/strict"),test=require("node:test");
const {geminiModel,makeRequest,parseModelResponse,validateModel,DEFAULT_MODEL}=require("../scripts/gemini_transport.cjs");
test("default Gemini model stays supported for new API projects",()=>assert.equal(DEFAULT_MODEL,"gemini-3.5-flash-lite"));
const good={role:"LUNA",assessment:"社群已有一篇可查公開貼文，但不能推論整體投資人多空共識。",confidence:"低",evidenceRefs:["SOCIAL"],uncertainties:["單一標題不能代表留言或市場共識"],noTrade:true};
test("authorized Gemini transport sends system/data in separate fields, never querystring key",()=>{
 const request=makeRequest({model:DEFAULT_MODEL,messages:[{role:"system",content:"不提供交易建議"},{role:"user",content:"公開市場資料"}],max_tokens:1000,temperature:.2});
 assert.match(request.url,/generativelanguage\.googleapis\.com\/v1beta\/models\/gemini-/);
 assert(!request.url.includes("key="));
 assert.equal(request.body.contents[0].role,"user");
 assert.equal(request.body.systemInstruction.parts[0].text,"不提供交易建議");
 assert.equal(request.body.generationConfig.responseMimeType,"application/json");
 assert.equal(request.body.generationConfig.responseSchema.properties.noTrade.type,"BOOLEAN");
});
test("a real shaped transport response returns structured content only",async()=>{
 let called=0;
 const payload=JSON.stringify(good);
 const fake=async(url,opts)=>{
  called++; assert(!url.includes("SECRET_TEST_KEY"));
  assert.equal(opts.headers["x-goog-api-key"],"SECRET_TEST_KEY");
  return {ok:true,status:200,json:async()=>({candidates:[{finishReason:"STOP",content:{parts:[{text:payload}]}}]})};
 };
 const raw=await geminiModel({model:DEFAULT_MODEL,messages:[{role:"system",content:"s"},{role:"user",content:"u"}]}, {apiKey:"SECRET_TEST_KEY",fetchFn:fake});
 assert.deepEqual(JSON.parse(raw),good);assert.equal(called,1);
});
test("no key means no network request and no pretend discussion",async()=>{
 let called=false;
 await assert.rejects(geminiModel({model:DEFAULT_MODEL,messages:[{role:"system",content:"s"},{role:"user",content:"u"}]},
 {apiKey:"",fetchFn:async()=>{called=true}}),/GEMINI_API_KEY/);
 assert.equal(called,false);
});
test("invalid model name rejects untrusted endpoint redirection",()=>{
 assert.throws(()=>validateModel("../delete"),/invalid/);
 assert.throws(()=>validateModel("https://example.com"),/invalid/);
});
test("non-JSON API response, blocked or malformed output all fail closed",async()=>{
 for(const candidate of [
  {candidates:[{finishReason:"STOP",content:{parts:[{text:"OK"}]}}]},
  {candidates:[{finishReason:"MAX_TOKENS",content:{parts:[{text:JSON.stringify(good)}]}}]},
  {candidates:[]}
 ])await assert.rejects(geminiModel({model:DEFAULT_MODEL,messages:[{role:"system",content:"s"},{role:"user",content:"u"}]},
 {apiKey:"x",fetchFn:async()=>({ok:true,status:200,json:async()=>candidate})}),/non-JSON|not complete|missing/);
});
test("quota errors fail clearly without reporting inference success",async()=>{
 await assert.rejects(geminiModel({model:DEFAULT_MODEL,messages:[{role:"system",content:"s"},{role:"user",content:"u"}]},
 {apiKey:"x",noSleep:true,fetchFn:async()=>({ok:false,status:429})}),/429/);
});
test("separate script's offline mock must not be claimed to be real inference",async()=>{
 const {selfTest}=require("../scripts/run_six_agent_llm.cjs");
 await selfTest();
});
