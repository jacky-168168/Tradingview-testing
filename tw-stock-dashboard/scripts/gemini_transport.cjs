#!/usr/bin/env node
/* Authorized Gemini transport for the read-only six-agent research meeting.
 * A real model API must return real structured content. Missing credentials, quota,
 * non-JSON responses, and blocked outputs all fail closed. No fallback mock on CI.
 */
"use strict";
const assert=require("node:assert/strict");
const API="https://generativelanguage.googleapis.com/v1beta/models/";
const DEFAULT_MODEL="gemini-2.5-flash-lite";
const OUTPUT_SCHEMA={
 type:"OBJECT",
 properties:{
  role:{type:"STRING",enum:["ATLAS","VEGA","ORION","LUNA","TITAN","NOVA"]},
  assessment:{type:"STRING"},
  confidence:{type:"STRING",enum:["低","中","高"]},
  evidenceRefs:{type:"ARRAY",items:{type:"STRING",enum:["G","RISK","NEWS","SOCIAL"]}},
  uncertainties:{type:"ARRAY",items:{type:"STRING"}},
  noTrade:{type:"BOOLEAN"}
 },
 required:["role","assessment","confidence","evidenceRefs","uncertainties","noTrade"]
};
function validateModel(name){
 if(typeof name!=="string"||!/^gemini-[a-z0-9.-]{1,56}$/i.test(name))throw Error("Gemini model name invalid");
 return name;
}
function makeRequest({model,messages,max_tokens,temperature}){
 model=validateModel(model||DEFAULT_MODEL);
 assert(Array.isArray(messages)&&messages.length===2&&messages[0].role==="system"&&messages[1].role==="user");
 const system=String(messages[0].content||"").slice(0,14000),user=String(messages[1].content||"").slice(0,24000);
 if(!system||!user)throw Error("LLM prompts empty");
 return {
  url:API+model+":generateContent",
  body:{
   systemInstruction:{parts:[{text:system}]},
   contents:[{role:"user",parts:[{text:user}]}],
   generationConfig:{temperature:typeof temperature==="number"?Math.max(0,Math.min(.5,temperature)):.2,
    maxOutputTokens:Math.max(512,Math.min(1800,Number(max_tokens)||1200)),
    responseMimeType:"application/json",responseSchema:OUTPUT_SCHEMA}
  }
 };
}
function parseModelResponse(json){
 if(!json||typeof json!=="object"||!Array.isArray(json.candidates)||!json.candidates.length)
  throw Error("Gemini response missing model candidates");
 const candidate=json.candidates[0],parts=candidate?.content?.parts;
 if(candidate?.finishReason&&candidate.finishReason!=="STOP")
  throw Error("Gemini output not complete: "+String(candidate.finishReason).slice(0,60));
 const text=Array.isArray(parts)?parts.filter(x=>typeof x.text==="string").map(x=>x.text).join(""):"";
 if(!text.trim())throw Error("Gemini response contains no verified text");
 try{const parsed=JSON.parse(text);if(!parsed||typeof parsed!=="object"||Array.isArray(parsed))throw Error("Not a JSON object");
  return text;
 }catch{throw Error("Gemini returned non-JSON content; not publishing model report")}
}
async function geminiModel(options,dependencies={}){
 const apiKey=dependencies.apiKey??process.env.GEMINI_API_KEY;
 if(typeof apiKey!=="string"||!apiKey.trim())throw Error("GEMINI_API_KEY secret is missing; model session was not executed");
 const fetchFn=dependencies.fetchFn??globalThis.fetch;
 if(typeof fetchFn!=="function")throw Error("fetch unavailable; model session was not executed");
 const req=makeRequest(options);
 const retries=2;
 for(let attempt=0;attempt<retries;attempt++){
  const response=await fetchFn(req.url,{method:"POST",
   headers:{"Content-Type":"application/json","Accept":"application/json","x-goog-api-key":apiKey},
   body:JSON.stringify(req.body),signal:AbortSignal.timeout(50000)});
  if((response.status===429||response.status>=500)&&attempt+1<retries){
   if(!dependencies.noSleep)await new Promise(resolve=>setTimeout(resolve,4000));
   continue;
  }
  if(!response.ok)throw Error("Gemini HTTP "+response.status+"; failed closed (check account quota/model/secret)");
  let json;
  try{json=await response.json()}
  catch{throw Error("Gemini returned invalid JSON over HTTP "+response.status+"; not verified")}
  return parseModelResponse(json);
 }
 throw Error("Gemini inference retry limit reached");
}
module.exports={geminiModel,makeRequest,parseModelResponse,validateModel,DEFAULT_MODEL,OUTPUT_SCHEMA};
