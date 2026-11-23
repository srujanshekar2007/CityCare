import dotenv from 'dotenv'
import { createClient } from '@supabase/supabase-js'
import { fileURLToPath } from 'node:url'

// Load only the backend environment file. Never import these values into Vite.
dotenv.config({ path: fileURLToPath(new URL('../apps/api/.env', import.meta.url)) })

const { SUPABASE_URL, SUPABASE_SECRET_KEY } = process.env
if (!SUPABASE_URL || !SUPABASE_SECRET_KEY) {
  throw new Error('Set SUPABASE_URL and SUPABASE_SECRET_KEY in apps/api/.env before running this script.')
}

const projectUrl = new URL(SUPABASE_URL)
if (projectUrl.pathname === '/rest/v1' || projectUrl.pathname === '/rest/v1/') {
  projectUrl.pathname = '/'
  projectUrl.search = ''
  projectUrl.hash = ''
  console.warn('SUPABASE_URL contains the REST endpoint suffix; using its project base URL for Auth Admin requests.')
} else if (projectUrl.pathname !== '/' || projectUrl.search || projectUrl.hash) {
  throw new Error('SUPABASE_URL must be the project base URL without a REST/Auth path, query, or fragment.')
}

const supabase = createClient(projectUrl.toString(), SUPABASE_SECRET_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
})

const demoAccounts = [
  { email: 'admin@citycare.demo', passwordEnv: 'CITYCARE_DEMO_ADMIN_PASSWORD', fullName: 'City Administrator', role: 'admin' },
  { email: 'worker@citycare.demo', passwordEnv: 'CITYCARE_DEMO_WORKER_PASSWORD', fullName: 'Ravi Kumar', role: 'worker' },
  { email: 'citizen@citycare.demo', passwordEnv: 'CITYCARE_DEMO_CITIZEN_PASSWORD', fullName: 'Asha Rao', role: 'citizen' },
]

async function listAllAuthUsers() {
  const users = []
  for (let page = 1; ; page += 1) {
    const { data, error } = await supabase.auth.admin.listUsers({ page, perPage: 1000 })
    if (error) {
      const status = Number.isInteger(error.status) ? ` (HTTP ${error.status})` : ''
      throw new Error(`Could not inspect Supabase Auth users${status}. No demo accounts were changed; check the project URL, Secret Key, and Supabase Auth service status.`)
    }
    users.push(...data.users)
    if (data.users.length < 1000) return users
  }
}

async function getProfileByEmail(email) {
  const { data, error } = await supabase.from('profiles').select('id,email,full_name,role').eq('email', email)
  if (error) throw new Error(`Could not inspect the profile for ${email}.`)
  if (data.length > 1) throw new Error(`Multiple profile rows use ${email}; resolve that conflict before provisioning.`)
  return data[0] ?? null
}

async function ensureAuthUser(account, authUsers, profileByEmail) {
  const matches = authUsers.filter((user) => user.email?.toLowerCase() === account.email)
  if (matches.length > 1) throw new Error(`Multiple Auth users use ${account.email}; resolve that conflict before provisioning.`)

  let user = matches[0] ?? null
  if (!user && profileByEmail) {
    // The existing profile id is authoritative when Auth and profiles disagree.
    // Reuse that Auth id if possible; never delete or detach the existing profile.
    const { data, error } = await supabase.auth.admin.getUserById(profileByEmail.id)
    if (error || !data.user) {
      throw new Error(`Profile for ${account.email} exists without a matching Auth user. No profile was changed.`)
    }
    user = data.user
  }

  if (user) {
    const conflictingEmailUser = authUsers.find((item) => item.email?.toLowerCase() === account.email && item.id !== user.id)
    if (conflictingEmailUser) throw new Error(`Auth email conflict for ${account.email}.`)
    const { data, error } = await supabase.auth.admin.updateUserById(user.id, {
      email: account.email,
      password: account.password,
      email_confirm: true,
      user_metadata: { ...user.user_metadata, full_name: profileByEmail?.full_name || account.fullName },
    })
    if (error || !data.user) throw new Error(`Could not update the demo Auth user ${account.email}.`)
    user = data.user
  } else {
    // The database's existing auth.users trigger creates a citizen profile here.
    const { data, error } = await supabase.auth.admin.createUser({
      email: account.email,
      password: account.password,
      email_confirm: true,
      user_metadata: { full_name: account.fullName },
    })
    if (error || !data.user) throw new Error(`Could not create the demo Auth user ${account.email}.`)
    user = data.user
    authUsers.push(user)
  }

  if (profileByEmail && profileByEmail.id !== user.id) {
    throw new Error(`Auth id and existing profile id differ for ${account.email}; no profile was reassigned.`)
  }

  const { data: currentProfile, error: profileReadError } = await supabase
    .from('profiles')
    .select('id,email,full_name,role')
    .eq('id', user.id)
    .maybeSingle()
  if (profileReadError) throw new Error(`Could not verify the profile for ${account.email}.`)

  const emailProfile = await getProfileByEmail(account.email)
  if (emailProfile && emailProfile.id !== user.id) {
    throw new Error(`A different profile row already owns ${account.email}; no profile was overwritten.`)
  }

  const { error: profileWriteError } = await supabase.from('profiles').upsert({
    id: user.id,
    email: account.email,
    full_name: currentProfile?.full_name || profileByEmail?.full_name || account.fullName,
    role: account.role,
  }, { onConflict: 'id' })
  if (profileWriteError) throw new Error(`Could not set the ${account.role} profile for ${account.email}.`)

  const { data: verifiedUser, error: verifyAuthError } = await supabase.auth.admin.getUserById(user.id)
  if (verifyAuthError || !verifiedUser.user || verifiedUser.user.email?.toLowerCase() !== account.email || !verifiedUser.user.email_confirmed_at) {
    throw new Error(`Auth verification failed for ${account.email}.`)
  }
  const { data: verifiedProfile, error: verifyProfileError } = await supabase
    .from('profiles')
    .select('id,email,role')
    .eq('id', user.id)
    .single()
  if (verifyProfileError || verifiedProfile.email !== account.email || verifiedProfile.role !== account.role) {
    throw new Error(`Profile role verification failed for ${account.email}.`)
  }
  return account.email
}

const authUsers = await listAllAuthUsers()
for (const account of demoAccounts) {
  const password = process.env[account.passwordEnv]
  if (!password) throw new Error(`Set ${account.passwordEnv} in apps/api/.env before running this script.`)
  const profile = await getProfileByEmail(account.email)
  await ensureAuthUser({ ...account, password }, authUsers, profile)
  console.log(`Verified Auth user and ${account.role} profile: ${account.email}`)
}
console.log('Demo authentication provisioning completed successfully.')
