import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
const url=Deno.env.get('SUPABASE_URL')!
const serviceKey=Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
const adminPin=Deno.env.get('GOLDEN_FEEDBACK_ADMIN_PIN')
const db=createClient(url,serviceKey,{auth:{persistSession:false}})
const origin='https://chiraawork-hue.github.io'
const headers={'Access-Control-Allow-Origin':origin,'Access-Control-Allow-Headers':'content-type, authorization, apikey','Access-Control-Allow-Methods':'POST, OPTIONS','Content-Type':'application/json','Cache-Control':'no-store'}
const reply=(status:number,data:unknown)=>new Response(JSON.stringify(data),{status,headers})
function equalConstant(a:string,b:string){const x=new TextEncoder().encode(a),y=new TextEncoder().encode(b);let diff=x.length^y.length;for(let i=0;i<Math.max(x.length,y.length);i++)diff|=(x[i]||0)^(y[i]||0);return diff===0}
Deno.serve(async request=>{
 if(request.method==='OPTIONS')return new Response(null,{headers})
 if(request.method!=='POST')return reply(405,{error:'Method not allowed'})
 if(request.headers.get('origin')!==origin)return reply(403,{error:'Forbidden'})
 if(!adminPin||!/^[0-9]{6}$/.test(adminPin))return reply(503,{error:'Admin PIN not configured'})
 const ip=(request.headers.get('cf-connecting-ip')||request.headers.get('x-forwarded-for')?.split(',')[0]||'unknown').trim().slice(0,100)
 const encoder=new TextEncoder()
 const digest=await crypto.subtle.digest('SHA-256',encoder.encode(ip+'|'+(Deno.env.get('GOLDEN_FEEDBACK_RATE_SALT')||'')))
 const ipHash=Array.from(new Uint8Array(digest)).map(b=>b.toString(16).padStart(2,'0')).join('')
 const {data:attempt,error:readError}=await db.from('golden_feedback_login_attempts').select('failures,blocked_until').eq('ip_hash',ipHash).maybeSingle()
 if(readError)return reply(503,{error:'Rate limiter unavailable'})
 if(attempt?.blocked_until&&Date.parse(attempt.blocked_until)>Date.now())return reply(429,{error:'Too many attempts; try again later'})
 let body;try{body=await request.json()}catch{return reply(400,{error:'Invalid request'})}
 const pin=typeof body.pin==='string'?body.pin:''
 if(!/^[0-9]{6}$/.test(pin)||!equalConstant(pin,adminPin)){
  const failures=(attempt?.failures||0)+1
  const blocked_until=failures>=5?new Date(Date.now()+15*60*1000).toISOString():null
  await db.from('golden_feedback_login_attempts').upsert({ip_hash:ipHash,failures:blocked_until?0:failures,blocked_until,updated_at:new Date().toISOString()},{onConflict:'ip_hash'})
  return reply(401,{error:'PIN incorrect'})
 }
 await db.from('golden_feedback_login_attempts').delete().eq('ip_hash',ipHash)
 const {data,error}=await db.from('planora_gold_feedback').select('*').order('created_at',{ascending:false}).limit(1000)
 if(error)return reply(503,{error:'Feedback unavailable'})
 const feedback=await Promise.all((data||[]).map(async row=>{
  if(!row.screenshot_path)return row
  const {data:signed}=await db.storage.from('planora-gold-feedback').createSignedUrl(row.screenshot_path,120)
  return {...row,screenshot_url:signed?.signedUrl||null}
 }))
 return reply(200,{feedback})
})