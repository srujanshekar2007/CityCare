import dotenv from 'dotenv'
dotenv.config({ path: new URL('../.env', import.meta.url) })
import express from 'express'
import cors from 'cors'
import { createClient } from '@supabase/supabase-js'
import { z } from 'zod'

const env = z.object({SUPABASE_URL:z.string().url(),SUPABASE_PUBLISHABLE_KEY:z.string().min(1),PORT:z.coerce.number().default(4000),WEB_ORIGIN:z.string().default('http://localhost:5173')}).safeParse(process.env)
function projectBaseUrl(value:string){const url=new URL(value);if(url.pathname==='/rest/v1'||url.pathname==='/rest/v1/')url.pathname='/';if(url.pathname!=='/'||url.search||url.hash)throw new Error('SUPABASE_URL must be the project base URL');return url.origin}
const app=express()
app.disable('x-powered-by')
app.use(cors({origin:env.success?env.data.WEB_ORIGIN:'http://localhost:5173'}))
app.use(express.json({limit:'32kb'}))
app.get('/health',(_req,res)=>res.json({status:'ok',service:'citycare-api'}))
if(env.success){
 const supabase=createClient(projectBaseUrl(env.data.SUPABASE_URL),env.data.SUPABASE_PUBLISHABLE_KEY,{auth:{persistSession:false}})
 app.use(async(req,res,next)=>{
   if(req.path==='/health') return next()
   const token=req.header('authorization')?.replace(/^Bearer\s+/i,'')
   if(!token)return res.status(401).json({error:'Authentication required'})
   const {data:{user},error}=await supabase.auth.getUser(token)
   if(error||!user){console.warn('[CityCare API auth] Token verification failed',{status:error?.status??null,code:error?.code??null});return res.status(401).json({error:'Invalid session'})}
   const userDb=createClient(projectBaseUrl(env.data.SUPABASE_URL),env.data.SUPABASE_PUBLISHABLE_KEY,{global:{headers:{Authorization:`Bearer ${token}`}},auth:{persistSession:false}})
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
