import 'dotenv/config'
import { createClient } from '@supabase/supabase-js'

const { SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY } = process.env
if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) throw new Error('Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in the server environment.')
const db = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, { auth: { persistSession: false } })
const accounts = [
  { email: 'admin@citycare.demo', password: 'Admin@123', full_name: 'City Administrator', role: 'admin' },
  { email: 'worker@citycare.demo', password: 'Worker@123', full_name: 'Ravi Kumar', role: 'worker' },
  { email: 'citizen@citycare.demo', password: 'Citizen@123', full_name: 'Asha Rao', role: 'citizen' },
]

async function ensureUser(account) {
  const { data: page, error: listError } = await db.auth.admin.listUsers({ page: 1, perPage: 1000 })
  if (listError) throw listError
  let user = page.users.find((u) => u.email?.toLowerCase() === account.email)
  if (!user) {
    const { data, error } = await db.auth.admin.createUser({ email: account.email, password: account.password, email_confirm: true, user_metadata: { full_name: account.full_name } })
    if (error) throw error
    user = data.user
  } else {
    const { data, error } = await db.auth.admin.updateUserById(user.id, { password: account.password, email_confirm: true, user_metadata: { full_name: account.full_name } })
    if (error) throw error
    user = data.user
  }
  const { error: profileError } = await db.from('profiles').upsert({ id: user.id, full_name: account.full_name, email: account.email, role: account.role, active: true }, { onConflict: 'id' })
  if (profileError) throw profileError
  return user
}

const users = {}
for (const account of accounts) users[account.role] = await ensureUser(account)
const { data: zone, error: zoneError } = await db.from('administrative_zones').upsert({ name: 'Central Bengaluru Demo', description: 'Fictional sample zone for demonstration' }, { onConflict: 'name' }).select().single()
if (zoneError) throw zoneError
const { error: workerError } = await db.from('workers').upsert({ user_id: users.worker.id, zone_id: zone.id, specialization: ['Road Damage / Potholes', 'Streetlight Problems'], availability: 'available' }, { onConflict: 'user_id' })
if (workerError) throw workerError
const { data: categories, error: categoryError } = await db.from('issue_categories').select('id,name')
if (categoryError) throw categoryError
const categoryId = (name) => categories.find((c) => c.name === name)?.id
const examples = [
  { title: 'Pothole near 12th Cross', category: 'Road Damage / Potholes', description: 'Demo report: a pothole is affecting the left lane near the corner.', latitude: 12.9784, longitude: 77.6408, location_description: '12th Cross, Indiranagar, Bengaluru', status: 'Reported', priority: 'High' },
  { title: 'Streetlight out on 5th Main', category: 'Streetlight Problems', description: 'Demo report: the streetlight has not worked for several evenings.', latitude: 12.9251, longitude: 77.5838, location_description: '5th Main Road, Jayanagar, Bengaluru', status: 'Resolution Submitted', priority: 'Normal' },
  { title: 'Water leak near public tap', category: 'Water Leakage', description: 'Demo report: water is leaking continuously from the roadside connection.', latitude: 13.0033, longitude: 77.5700, location_description: 'Malleshwaram, Bengaluru', status: 'In Progress', priority: 'Urgent' },
]
for (const example of examples) {
  const { data: existing, error: findError } = await db.from('complaints').select('id').eq('citizen_id', users.citizen.id).eq('location_description', example.location_description).limit(1)
  if (findError) throw findError
  if (existing.length) continue
  const { data: complaint, error } = await db.from('complaints').insert({ ...example, citizen_id: users.citizen.id, category_id: categoryId(example.category), zone_id: zone.id, deadline: new Date(Date.now() + 36 * 60 * 60 * 1000).toISOString() }).select().single()
  if (error) throw error
  if (['In Progress', 'Resolution Submitted'].includes(example.status)) {
    const { error: assignmentError } = await db.from('worker_assignments').insert({ complaint_id: complaint.id, worker_id: users.worker.id, admin_id: users.admin.id, deadline: new Date(Date.now() + 36 * 60 * 60 * 1000).toISOString() })
    if (assignmentError) throw assignmentError
  }
}
console.log('Demo accounts and sample complaints are provisioned. Sign in with the documented demo credentials and verify each role.')
