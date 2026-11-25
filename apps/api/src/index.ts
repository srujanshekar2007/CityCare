import dotenv from 'dotenv'
dotenv.config({ path: new URL('../.env', import.meta.url) })
import express from 'express'
import cors from 'cors'
import { createClient } from '@supabase/supabase-js'
import { z } from 'zod'

const env = z.object({SUPABASE_URL:z.string().url(),SUPABASE_PUBLISHABLE_KEY:z.string().min(1),PORT:z.coerce.number().default(4000),WEB_ORIGIN:z.string().default('http://localhost:5173'),ML_SERVICE_URL:z.string().default('http://127.0.0.1:8001'),ML_SERVICE_TOKEN:z.string().optional(),ML_REQUEST_TIMEOUT_MS:z.coerce.number().int().min(500).max(30000).default(8000),ML_MAX_CANDIDATES:z.coerce.number().int().min(1).max(300).default(250)}).safeParse(process.env)
function projectBaseUrl(value:string){const url=new URL(value);if(url.pathname==='/rest/v1'||url.pathname==='/rest/v1/')url.pathname='/';if(url.pathname!=='/'||url.search||url.hash)throw new Error('SUPABASE_URL must be the project base URL');return url.origin}
const app=express()
app.disable('x-powered-by')
app.use(cors({origin:env.success?env.data.WEB_ORIGIN:'http://localhost:5173'}))
app.use(express.json({limit:'32kb'}))
app.get('/health',(_req,res)=>res.json({status:'ok',service:'citycare-api'}))
if(env.success){
 const config=env.data
 const supabase=createClient(projectBaseUrl(config.SUPABASE_URL),config.SUPABASE_PUBLISHABLE_KEY,{auth:{persistSession:false}})
 async function callIntelligence(path:string,payload?:unknown){
   if(!config.ML_SERVICE_TOKEN||config.ML_SERVICE_TOKEN.length<32)return {ok:false as const,status:503,data:{error:'Intelligence service is not configured'}}
   const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),config.ML_REQUEST_TIMEOUT_MS)
   try{
     const response=await fetch(new URL(path,config.ML_SERVICE_URL.endsWith('/')?config.ML_SERVICE_URL:`${config.ML_SERVICE_URL}/`),{method:payload?'POST':'GET',headers:{Authorization:`Bearer ${config.ML_SERVICE_TOKEN}`,...(payload?{'Content-Type':'application/json'}:{})},...(payload?{body:JSON.stringify(payload)}:{}),signal:controller.signal})
     let data:any=null;try{data=await response.json()}catch{data=null}
     return response.ok?{ok:true as const,status:response.status,data}:{ok:false as const,status:response.status,data:{error:'Intelligence service rejected the request'}}
   }catch(error){const timedOut=error instanceof Error&&error.name==='AbortError';console.warn('[CityCare intelligence] Service request failed',{timedOut,errorType:error instanceof Error?error.name:'UnknownError'});return {ok:false as const,status:503,data:{error:timedOut?'Intelligence service timed out':'Intelligence service unavailable'}}}
   finally{clearTimeout(timer)}
 }
 app.use(async(req,res,next)=>{
   if(req.path==='/health') return next()
   const token=req.header('authorization')?.replace(/^Bearer\s+/i,'')
   if(!token)return res.status(401).json({error:'Authentication required'})
   const {data:{user},error}=await supabase.auth.getUser(token)
   if(error||!user){console.warn('[CityCare API auth] Token verification failed',{status:error?.status??null,code:error?.code??null});return res.status(401).json({error:'Invalid session'})}
   const userDb=createClient(projectBaseUrl(config.SUPABASE_URL),config.SUPABASE_PUBLISHABLE_KEY,{global:{headers:{Authorization:`Bearer ${token}`}},auth:{persistSession:false}})
   const {data:profile,error:profileError}=await userDb.from('profiles').select('id,role').eq('id',user.id).single()
   if(profileError)console.warn('[CityCare API auth] Profile lookup failed',{code:profileError.code??null})
   if(!profile)return res.status(403).json({error:'Account unavailable'})
   res.locals.user=user;res.locals.profile=profile;res.locals.db=userDb;next()
 })
 app.get('/api/me',(req,res)=>res.json({user:res.locals.user,profile:res.locals.profile}))
 app.get('/api/complaints',async(req,res)=>{
   const schema=z.object({status:z.enum(['Reported','Under Review','Verified','Assigned','In Progress','Resolution Submitted','Resolved','Rejected']).optional(),limit:z.coerce.number().int().min(1).max(100).default(25)})
   const parsed=schema.safeParse(req.query);if(!parsed.success)return res.status(400).json({error:'Invalid query'})
   let query=res.locals.db.from('complaints').select('*,issue_categories(name),profiles!complaints_citizen_id_fkey(full_name),worker_assignments(worker_id,deadline,assignment_status)').order('submitted_at',{ascending:false}).limit(parsed.data.limit)
   if(parsed.data.status)query=query.eq('status',parsed.data.status)
   const {data,error}=await query;if(error)return res.status(400).json({error:'Unable to load complaints'})
   res.json({complaints:data})
 })
 const duplicateAnalysisSchema=z.object({complaint_id:z.string().uuid(),top_k:z.coerce.number().int().min(1).max(50).default(20)}).strict()
 app.post('/api/intelligence/duplicates/analyze',async(req,res)=>{
   if(!['admin','citizen'].includes(res.locals.profile.role))return res.status(403).json({error:'Administrator or citizen access required'})
   const parsed=duplicateAnalysisSchema.safeParse(req.body);if(!parsed.success)return res.status(400).json({error:'Invalid complaint analysis request'})
   const db=res.locals.db
   const {data:complaint,error:complaintError}=await db.from('complaints').select('id,complaint_number,citizen_id,description,category_id,latitude,longitude,location_description,submitted_at,issue_categories(name)').eq('id',parsed.data.complaint_id).maybeSingle()
   if(complaintError||!complaint)return res.status(404).json({error:'Complaint is unavailable to this account'})
   if(res.locals.profile.role==='citizen'&&complaint.citizen_id!==res.locals.user.id)return res.status(403).json({error:'You can only analyze a complaint you submitted'})
   let candidates:any[]=[]
   for(let start=0;start<config.ML_MAX_CANDIDATES;start+=1000){
     const end=Math.min(start+999,config.ML_MAX_CANDIDATES-1)
     const {data,error}=await db.from('complaints').select('id,complaint_number,description,category_id,latitude,longitude,location_description,submitted_at,issue_categories(name)').neq('id',complaint.id).order('submitted_at',{ascending:false}).range(start,end)
     if(error)return res.status(503).json({error:'Complaint comparison data is unavailable under the current database permissions'})
     candidates.push(...(data??[]));if((data??[]).length<end-start+1)break
   }
   const mapRecord=(row:any)=>({id:row.id,complaint_number:row.complaint_number,description:row.description,category_id:row.category_id,category:row.issue_categories?.name??null,latitude:row.latitude===null?null:Number(row.latitude),longitude:row.longitude===null?null:Number(row.longitude),location_description:row.location_description,submitted_at:row.submitted_at})
   const result=await callIntelligence('/api/v1/duplicates/analyze',{complaint:mapRecord(complaint),candidates:candidates.map(mapRecord),top_k:parsed.data.top_k})
   if(!result.ok)return res.status(result.status===401?503:result.status).json({error:result.data.error??'Duplicate analysis is unavailable; complaint workflow is unaffected'})
   res.json({...result.data,comparison_scope:res.locals.profile.role==='admin'?'administrator RLS-visible complaints':'complaints visible to the submitting citizen under RLS',candidate_limit_reached:candidates.length>=config.ML_MAX_CANDIDATES})
 })
 const hotspotQuerySchema=z.object({start_date:z.string().datetime().optional(),end_date:z.string().datetime().optional(),category_id:z.string().uuid().optional(),zone_id:z.string().uuid().optional(),priority:z.enum(['Low','Normal','High','Urgent']).optional(),status:z.enum(['Reported','Under Review','Verified','Assigned','In Progress','Resolution Submitted','Resolved','Rejected']).optional(),epsilon_meters:z.coerce.number().gt(0).max(50000).default(500),min_samples:z.coerce.number().int().min(2).max(100).default(3),limit:z.coerce.number().int().min(1).max(5000).default(2000)}).strict()
 app.get('/api/intelligence/hotspots',async(req,res)=>{
   if(res.locals.profile.role!=='admin')return res.status(403).json({error:'Administrator access required'})
   const parsed=hotspotQuerySchema.safeParse(req.query);if(!parsed.success)return res.status(400).json({error:'Invalid hotspot filters'})
   const filter=parsed.data;let query=res.locals.db.from('complaints').select('id,complaint_number,description,category_id,latitude,longitude,submitted_at,issue_categories(name)').order('submitted_at',{ascending:false})
   if(filter.start_date)query=query.gte('submitted_at',filter.start_date);if(filter.end_date)query=query.lte('submitted_at',filter.end_date);if(filter.category_id)query=query.eq('category_id',filter.category_id);if(filter.zone_id)query=query.eq('zone_id',filter.zone_id);if(filter.priority)query=query.eq('priority',filter.priority);if(filter.status)query=query.eq('status',filter.status)
   const complaints:any[]=[]
   for(let start=0;start<filter.limit;start+=1000){const end=Math.min(start+999,filter.limit-1),{data,error}=await query.range(start,end);if(error)return res.status(503).json({error:'Hotspot input is unavailable under the current database permissions'});complaints.push(...(data??[]));if((data??[]).length<end-start+1)break}
   const mapped=complaints.map((row:any)=>({id:row.id,complaint_number:row.complaint_number,category_id:row.category_id,category:row.issue_categories?.name??null,latitude:row.latitude===null?null:Number(row.latitude),longitude:row.longitude===null?null:Number(row.longitude),submitted_at:row.submitted_at}))
   const result=await callIntelligence('/api/v1/hotspots/analyze',{complaints:mapped,epsilon_meters:filter.epsilon_meters,min_samples:filter.min_samples,start_date:filter.start_date,end_date:filter.end_date,category_id:filter.category_id})
   if(!result.ok)return res.status(result.status===401?503:result.status).json({error:result.data.error??'Hotspot analysis is unavailable'})
   res.json({...result.data,record_scope:'administrator RLS-visible complaints',input_limit:filter.limit,limit_reached:complaints.length>=filter.limit})
 })
 app.get('/api/intelligence/model-info',async(_req,res)=>{if(res.locals.profile.role!=='admin')return res.status(403).json({error:'Administrator access required'});const result=await callIntelligence('/api/v1/model/info');if(!result.ok)return res.status(result.status===401?503:result.status).json({error:result.data.error??'Model information unavailable'});res.json(result.data)})
 app.get('/api/intelligence/evaluation',async(_req,res)=>{if(res.locals.profile.role!=='admin')return res.status(403).json({error:'Administrator access required'});const result=await callIntelligence('/api/v1/evaluation/summary');if(!result.ok)return res.status(result.status===401?503:result.status).json({error:result.data.error??'Model evaluation is unavailable'});res.json(result.data)})
 app.post('/api/complaints',async(req,res)=>{
   if(res.locals.profile.role!=='citizen')return res.status(403).json({error:'Citizen access required'})
   const schema=z.object({category_id:z.string().uuid(),description:z.string().trim().min(1).max(5000),latitude:z.number().min(-90).max(90),longitude:z.number().min(-180).max(180),location_description:z.string().trim().min(1).max(240)})
   const parsed=schema.safeParse(req.body);if(!parsed.success)return res.status(400).json({error:'Invalid complaint details',fields:parsed.error.flatten().fieldErrors})
   const {data,error}=await res.locals.db.from('complaints').insert({...parsed.data,citizen_id:res.locals.user.id,status:'Reported'}).select().single()
   if(error)return res.status(400).json({error:'Unable to submit complaint'})
   res.status(201).json({complaint:data})
 })
 app.post('/api/complaints/:id/assign',async(req,res)=>{
   if(res.locals.profile.role!=='admin')return res.status(403).json({error:'Administrator access required'})
   const schema=z.object({worker_id:z.string().uuid(),deadline:z.string().datetime(),instructions:z.string().trim().max(2000).optional()})
   const parsed=schema.safeParse(req.body);if(!parsed.success)return res.status(400).json({error:'Invalid assignment details'})
   const {data,error}=await res.locals.db.rpc('assign_complaint',{target_complaint:req.params.id,target_worker:parsed.data.worker_id,target_deadline:parsed.data.deadline,target_instructions:parsed.data.instructions??null})
   if(error)return res.status(400).json({error:'Unable to assign this complaint'})
   res.status(201).json({assignment_id:data})
 })
 app.patch('/api/complaints/:id/status',async(req,res)=>{
   const schema=z.object({status:z.enum(['Under Review','Verified','Assigned','In Progress','Resolution Submitted','Resolved','Rejected']),remarks:z.string().trim().max(2000).optional(),rejection_reason:z.string().trim().min(1).max(1000).optional()})
   const parsed=schema.safeParse(req.body);if(!parsed.success)return res.status(400).json({error:'Invalid status update'})
   const {data:current,error:readError}=await res.locals.db.from('complaints').select('id,status,citizen_id').eq('id',req.params.id).single()
   if(readError||!current)return res.status(404).json({error:'Complaint not found'})
   const role=res.locals.profile.role as string;const next=parsed.data.status
   const admin=role==='admin',worker=role==='worker'&&await res.locals.db.rpc('is_assigned_to',{target:current.id}).then((r:any)=>r.data===true)
   const allowed=admin|| (worker&&['In Progress','Resolution Submitted'].includes(next))
   if(!allowed)return res.status(403).json({error:'Not authorized for this transition'})
   if(next==='Rejected'&&!parsed.data.rejection_reason)return res.status(400).json({error:'A rejection reason is required'})
   if(next==='Resolved'&&role!=='admin')return res.status(403).json({error:'Only an admin can close a complaint'})
   const update:any={status:next,updated_at:new Date().toISOString()};if(parsed.data.remarks&&role==='admin')update.admin_remarks=parsed.data.remarks;if(parsed.data.rejection_reason)update.rejection_reason=parsed.data.rejection_reason;if(next==='Resolved')update.resolved_at=new Date().toISOString()
   const {data,error}=await res.locals.db.from('complaints').update(update).eq('id',current.id).select().single()
   if(error)return res.status(400).json({error:'Status transition rejected by policy'})
   if(parsed.data.remarks&&role==='worker'){
     const {error:noteError}=await res.locals.db.from('complaint_updates').insert({complaint_id:current.id,actor_id:res.locals.user.id,remarks:parsed.data.remarks})
     if(noteError)return res.status(500).json({error:'Status saved but progress note could not be recorded'})
   }
   res.json({complaint:data})
 })
}
app.use((_req,res)=>res.status(404).json({error:'Not found'}))
const port=env.success?env.data.PORT:4000
app.listen(port,'0.0.0.0',()=>console.log(`CityCare API listening on ${port}`))
