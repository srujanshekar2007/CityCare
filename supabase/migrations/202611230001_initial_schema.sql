create extension if not exists pgcrypto;

create type public.app_role as enum ('admin','worker','citizen');
create type public.complaint_status as enum ('Reported','Under Review','Verified','Assigned','In Progress','Resolution Submitted','Resolved','Rejected');
create type public.complaint_priority as enum ('Low','Normal','High','Urgent');

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text not null,
  email text not null unique,
  phone text,
  role public.app_role not null default 'citizen',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create table public.administrative_zones (
  id uuid primary key default gen_random_uuid(), name text not null unique,
  description text, is_active boolean not null default true, created_at timestamptz not null default now()
);
create table public.issue_categories (
  id uuid primary key default gen_random_uuid(),
  name text not null unique, description text, is_active boolean not null default true,
  created_at timestamptz not null default now()
);
insert into public.issue_categories(name) values
 ('Road Damage / Potholes'),('Garbage / Waste Management'),('Water Leakage'),('Drainage / Sewage Problems'),('Streetlight Problems'),('Footpath / Sidewalk Damage'),('Public Facility Problems'),('Traffic Infrastructure'),('Other');
create table public.workers (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null unique references public.profiles(id) on delete cascade,
  zone_id uuid references public.administrative_zones(id) on delete set null,
  specialization text, availability text not null default 'available' check (availability in ('available','busy','unavailable')),
  created_at timestamptz not null default now()
);
create table public.complaints (
  id uuid primary key default gen_random_uuid(), complaint_number bigint generated always as identity unique,
  citizen_id uuid not null references public.profiles(id), category_id uuid not null references public.issue_categories(id),
  description text not null check (length(trim(description)) > 0), latitude numeric(9,6) not null check (latitude between -90 and 90), longitude numeric(9,6) not null check (longitude between -180 and 180),
  location_description text not null, zone_id uuid references public.administrative_zones(id) on delete set null,
  priority public.complaint_priority not null default 'Normal', status public.complaint_status not null default 'Reported',
  rejection_reason text, admin_remarks text, deadline timestamptz, submitted_at timestamptz not null default now(), updated_at timestamptz not null default now(), resolved_at timestamptz,
  duplicate_of uuid references public.complaints(id) on delete set null,
  check (status <> 'Rejected' or (rejection_reason is not null and length(trim(rejection_reason)) > 0))
);
create index complaints_citizen_idx on public.complaints(citizen_id, submitted_at desc);
create index complaints_status_idx on public.complaints(status, submitted_at desc);
create index complaints_location_idx on public.complaints(latitude, longitude);
create index complaints_zone_idx on public.complaints(zone_id, status);
create table public.complaint_media (
  id uuid primary key default gen_random_uuid(), complaint_id uuid not null references public.complaints(id) on delete cascade,
  uploader_id uuid not null references public.profiles(id), storage_path text not null unique,
  media_kind text not null check (media_kind in ('citizen','before','during','after','resolution')),
  mime_type text not null check (mime_type in ('image/jpeg','image/png','image/webp')),
  size_bytes bigint not null check (size_bytes > 0 and size_bytes <= 10485760), created_at timestamptz not null default now()
);
create table public.complaint_updates (
  id uuid primary key default gen_random_uuid(), complaint_id uuid not null references public.complaints(id) on delete cascade,
  actor_id uuid references public.profiles(id), previous_status public.complaint_status, new_status public.complaint_status,
  remarks text, created_at timestamptz not null default now()
);
create index complaint_updates_history_idx on public.complaint_updates(complaint_id, created_at);
create table public.worker_assignments (
  id uuid primary key default gen_random_uuid(), complaint_id uuid not null references public.complaints(id) on delete cascade,
  worker_id uuid not null references public.workers(profile_id), admin_id uuid not null references public.profiles(id),
  assigned_at timestamptz not null default now(), deadline timestamptz not null,
  assignment_status text not null default 'active' check (assignment_status in ('active','completed','reassigned','cancelled')),
  instructions text
);
create index assignments_worker_idx on public.worker_assignments(worker_id, assignment_status);
create table public.work_evidence (
  id uuid primary key default gen_random_uuid(), complaint_id uuid not null references public.complaints(id) on delete cascade,
  assignment_id uuid not null references public.worker_assignments(id), uploader_id uuid not null references public.profiles(id),
  storage_path text not null unique, phase text not null check (phase in ('before','during','after','resolution')),
  caption text, created_at timestamptz not null default now()
);
create table public.notifications (
  id uuid primary key default gen_random_uuid(), user_id uuid not null references public.profiles(id) on delete cascade,
  complaint_id uuid references public.complaints(id) on delete cascade, title text not null, body text not null,
  read_at timestamptz, created_at timestamptz not null default now()
);
create index notifications_user_idx on public.notifications(user_id, created_at desc);
create table public.sla_policies (
  id uuid primary key default gen_random_uuid(), category_id smallint references public.issue_categories(id),
  priority public.complaint_priority not null, hours integer not null check (hours between 1 and 2160),
  unique(category_id, priority)
);
create table public.escalation_history (
  id uuid primary key default gen_random_uuid(), complaint_id uuid not null references public.complaints(id) on delete cascade,
  message text not null, created_at timestamptz not null default now()
);
create table public.feedback (
  id uuid primary key default gen_random_uuid(), complaint_id uuid not null unique references public.complaints(id) on delete cascade,
  citizen_id uuid not null references public.profiles(id), rating smallint not null check (rating between 1 and 5), comment text,
  created_at timestamptz not null default now()
);
create table public.audit_logs (
  id uuid primary key default gen_random_uuid(), actor_id uuid references public.profiles(id), action text not null,
  entity_type text not null, entity_id uuid, details jsonb not null default '{}', created_at timestamptz not null default now()
);

create or replace function public.current_role() returns public.app_role language sql stable security definer set search_path = public as $$ select role from public.profiles where id = auth.uid() $$;
create or replace function public.is_admin() returns boolean language sql stable security definer set search_path = public as $$ select coalesce(public.current_role() = 'admin', false) $$;
create or replace function public.is_assigned_to(target uuid) returns boolean language sql stable security definer set search_path = public as $$ select exists(select 1 from public.worker_assignments where complaint_id=target and worker_id=auth.uid() and assignment_status='active') $$;

alter table public.profiles enable row level security;
alter table public.administrative_zones enable row level security;
alter table public.issue_categories enable row level security;
alter table public.workers enable row level security;
alter table public.complaints enable row level security;
alter table public.complaint_media enable row level security;
alter table public.complaint_updates enable row level security;
alter table public.worker_assignments enable row level security;
alter table public.work_evidence enable row level security;
alter table public.notifications enable row level security;
alter table public.sla_policies enable row level security;
alter table public.escalation_history enable row level security;
alter table public.feedback enable row level security;
alter table public.audit_logs enable row level security;

create policy "profile self or admin read" on public.profiles for select to authenticated using (id=auth.uid() or public.is_admin() or exists(select 1 from public.worker_assignments a where a.worker_id=auth.uid() and a.complaint_id in (select c.id from public.complaints c where c.citizen_id=profiles.id)));
create policy "profile self update safe fields" on public.profiles for update to authenticated using (id=auth.uid()) with check (id=auth.uid() and role=public.current_role());
create policy "zones authenticated read" on public.administrative_zones for select to authenticated using (true);
create policy "zones admin manage" on public.administrative_zones for all to authenticated using (public.is_admin()) with check (public.is_admin());
create policy "categories read" on public.issue_categories for select to authenticated using (true);
create policy "categories admin manage" on public.issue_categories for all to authenticated using (public.is_admin()) with check (public.is_admin());
create policy "workers read relevant" on public.workers for select to authenticated using (profile_id=auth.uid() or public.is_admin());
create policy "workers admin manage" on public.workers for all to authenticated using (public.is_admin()) with check (public.is_admin());
create policy "complaints citizen/admin/assigned read" on public.complaints for select to authenticated using (citizen_id=auth.uid() or public.is_admin() or public.is_assigned_to(id));
create policy "citizens create own reported complaint" on public.complaints for insert to authenticated with check (public.current_role()='citizen' and citizen_id=auth.uid() and status='Reported' and rejection_reason is null and resolved_at is null);
create policy "admins manage complaints" on public.complaints for update to authenticated using (public.is_admin()) with check (public.is_admin());
create policy "assigned workers advance active task" on public.complaints for update to authenticated using (public.is_assigned_to(id)) with check (public.is_assigned_to(id) and status in ('In Progress','Resolution Submitted'));
create policy "citizen or admin read complaint media" on public.complaint_media for select to authenticated using (public.is_admin() or uploader_id=auth.uid() or exists(select 1 from public.complaints c where c.id=complaint_id and c.citizen_id=auth.uid()) or public.is_assigned_to(complaint_id));
create policy "authorized complaint media insert" on public.complaint_media for insert to authenticated with check (uploader_id=auth.uid() and (public.is_admin() or (public.current_role()='citizen' and media_kind='citizen' and exists(select 1 from public.complaints c where c.id=complaint_id and c.citizen_id=auth.uid())) or (public.current_role()='worker' and public.is_assigned_to(complaint_id))));
create policy "updates permitted read" on public.complaint_updates for select to authenticated using (public.is_admin() or exists(select 1 from public.complaints c where c.id=complaint_id and c.citizen_id=auth.uid()) or public.is_assigned_to(complaint_id));
create policy "authorized progress update" on public.complaint_updates for insert to authenticated with check (actor_id=auth.uid() and (public.is_admin() or public.is_assigned_to(complaint_id)));
create policy "assignments relevant read" on public.worker_assignments for select to authenticated using (worker_id=auth.uid() or public.is_admin());
create policy "assignments admin manage" on public.worker_assignments for all to authenticated using (public.is_admin()) with check (public.is_admin());
create policy "evidence relevant read" on public.work_evidence for select to authenticated using (public.is_admin() or uploader_id=auth.uid() or exists(select 1 from public.complaints c where c.id=complaint_id and c.citizen_id=auth.uid()));
create policy "assigned worker evidence insert" on public.work_evidence for insert to authenticated with check (uploader_id=auth.uid() and public.is_assigned_to(complaint_id));
create policy "own notifications" on public.notifications for all to authenticated using (user_id=auth.uid() or public.is_admin()) with check (user_id=auth.uid() or public.is_admin());
create policy "sla read" on public.sla_policies for select to authenticated using (true);
create policy "sla admin manage" on public.sla_policies for all to authenticated using (public.is_admin()) with check (public.is_admin());
create policy "escalations admin read" on public.escalation_history for select to authenticated using (public.is_admin());
create policy "feedback own read and insert" on public.feedback for select to authenticated using (citizen_id=auth.uid() or public.is_admin());
create policy "feedback own insert" on public.feedback for insert to authenticated with check (citizen_id=auth.uid() and exists(select 1 from public.complaints c where c.id=complaint_id and c.citizen_id=auth.uid() and c.status='Resolved'));
create policy "audit admin read" on public.audit_logs for select to authenticated using (public.is_admin());

-- Account roles are assigned only by trusted project provisioning; clients cannot write role during profile creation.
create or replace function public.on_auth_user_created() returns trigger language plpgsql security definer set search_path=public as $$
begin
 insert into public.profiles(id,full_name,email,role) values(new.id,coalesce(new.raw_user_meta_data->>'full_name','CityCare user'),new.email,'citizen');
 return new;
end $$;
create trigger auth_user_profile after insert on auth.users for each row execute procedure public.on_auth_user_created();

create or replace function public.record_complaint_change() returns trigger language plpgsql security definer set search_path=public as $$
begin
 if tg_op='INSERT' then
   insert into public.complaint_updates(complaint_id,actor_id,previous_status,new_status,remarks) values(new.id,auth.uid(),null,new.status,'Complaint submitted');
 elsif new.status is distinct from old.status then
   insert into public.complaint_updates(complaint_id,actor_id,previous_status,new_status,remarks) values(new.id,auth.uid(),old.status,new.status,case when new.status='Rejected' then new.rejection_reason else new.admin_remarks end);
   insert into public.notifications(user_id,complaint_id,title,body) values(new.citizen_id,new.id,'Complaint status updated','Your complaint is now '||new.status::text||'.');
 end if;
 return new;
end $$;
create trigger complaint_change_history after insert or update on public.complaints for each row execute procedure public.record_complaint_change();

create or replace function public.assign_complaint(target_complaint uuid,target_worker uuid,target_deadline timestamptz,target_instructions text default null)
returns uuid language plpgsql security definer set search_path=public as $$
declare complaint_row public.complaints%rowtype; assignment_key uuid;
begin
 if not public.is_admin() then raise exception 'Administrator access required'; end if;
 select * into complaint_row from public.complaints where id=target_complaint for update;
 if complaint_row.id is null then raise exception 'Complaint not found'; end if;
 if complaint_row.status not in ('Verified','Assigned') then raise exception 'Complaint must be verified before assignment'; end if;
 if target_deadline<=now() then raise exception 'Deadline must be in the future'; end if;
 if not exists(select 1 from public.workers w join public.profiles p on p.id=w.profile_id where w.profile_id=target_worker and p.role='worker' and w.availability<>'unavailable') then raise exception 'Worker is not active or available'; end if;
 update public.worker_assignments set assignment_status='reassigned' where complaint_id=target_complaint and assignment_status='active';
 insert into public.worker_assignments(complaint_id,worker_id,admin_id,deadline,instructions) values(target_complaint,target_worker,auth.uid(),target_deadline,target_instructions) returning id into assignment_key;
 update public.complaints set status='Assigned',deadline=target_deadline,updated_at=now() where id=target_complaint;
 insert into public.notifications(user_id,complaint_id,title,body) values(target_worker,target_complaint,'New task assigned','A civic issue has been assigned to you.');
 insert into public.audit_logs(actor_id,action,entity_type,entity_id,details) values(auth.uid(),'complaint.assigned','complaint',target_complaint,jsonb_build_object('worker_id',target_worker,'deadline',target_deadline,'assignment_id',assignment_key));
 return assignment_key;
end $$;

insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values('citycare-evidence','citycare-evidence',false,10485760,array['image/jpeg','image/png','image/webp'])
on conflict(id) do nothing;
create policy "evidence read by complaint access" on storage.objects for select to authenticated using (
 bucket_id='citycare-evidence' and exists(select 1 from public.complaint_media m where m.storage_path=name and (public.is_admin() or m.uploader_id=auth.uid() or exists(select 1 from public.complaints c where c.id=m.complaint_id and c.citizen_id=auth.uid()) or public.is_assigned_to(m.complaint_id)))
);
create policy "evidence owner upload" on storage.objects for insert to authenticated with check (
  bucket_id='citycare-evidence' and (storage.foldername(name))[1]=auth.uid()::text and (storage.foldername(name))[2] is not null
  and (storage.extension(name) in ('jpg','jpeg','png','webp'))
  and exists(select 1 from public.complaints c where c.id::text=(storage.foldername(name))[2] and (c.citizen_id=auth.uid() or public.is_admin() or public.is_assigned_to(c.id)))
);

create or replace function public.guard_complaint_update() returns trigger language plpgsql security definer set search_path=public as $$
declare actor_role public.app_role;
begin
 if coalesce(auth.role(),'')='service_role' then return new; end if;
 actor_role:=public.current_role();
 if actor_role='worker' then
   if new.citizen_id is distinct from old.citizen_id or new.category_id is distinct from old.category_id or new.description is distinct from old.description or new.latitude is distinct from old.latitude or new.longitude is distinct from old.longitude or new.location_description is distinct from old.location_description or new.zone_id is distinct from old.zone_id or new.priority is distinct from old.priority or new.deadline is distinct from old.deadline or new.rejection_reason is distinct from old.rejection_reason or new.admin_remarks is distinct from old.admin_remarks or new.resolved_at is distinct from old.resolved_at then
     raise exception 'Workers may only advance the assigned task status';
   end if;
   if not ((old.status='Assigned' and new.status='In Progress') or (old.status='In Progress' and new.status in ('In Progress','Resolution Submitted'))) then
     raise exception 'Invalid worker status transition';
   end if;
 elsif actor_role='admin' then
   if not ((old.status='Reported' and new.status in ('Under Review','Rejected')) or (old.status='Under Review' and new.status in ('Verified','Rejected')) or (old.status='Verified' and new.status='Assigned') or (old.status='Assigned' and new.status='Assigned') or (old.status='In Progress' and new.status='In Progress') or (old.status='Resolution Submitted' and new.status in ('Resolved','In Progress')) or (old.status=new.status)) then
     raise exception 'Invalid administrator status transition';
   end if;
 elsif actor_role is not null then
   raise exception 'This role cannot update complaints';
 end if;
 return new;
end $$;
create trigger complaint_update_guard before update on public.complaints for each row execute procedure public.guard_complaint_update();
