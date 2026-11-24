create or replace function public.assign_complaint(
  target_complaint uuid,
  target_worker uuid,
  target_deadline timestamptz,
  target_instructions text default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  complaint_row public.complaints%rowtype;
  worker_row public.workers%rowtype;
  assignment_key uuid;
begin
  if not public.is_citycare_admin() then
    raise exception 'Administrator access required';
  end if;

  select * into complaint_row
  from public.complaints
  where id = target_complaint
  for update;

  if complaint_row.id is null then
    raise exception 'Complaint not found';
  end if;
  if complaint_row.status not in ('Verified', 'Assigned') then
    raise exception 'Complaint must be verified before assignment';
  end if;
  if target_deadline <= now() then
    raise exception 'Deadline must be in the future';
  end if;

  select w.* into worker_row
  from public.workers w
  join public.profiles p on p.id = w.profile_id
  where w.profile_id = target_worker
    and p.role = 'worker'
    and w.availability <> 'unavailable';

  if worker_row.id is null then
    raise exception 'Worker is not available';
  end if;

  update public.worker_assignments
  set assignment_status = 'reassigned'
  where complaint_id = target_complaint
    and assignment_status in ('assigned', 'accepted', 'in_progress', 'submitted');

  insert into public.worker_assignments (
    complaint_id, worker_id, assigned_by, deadline, instructions, assignment_status
  ) values (
    target_complaint, worker_row.id, auth.uid(), target_deadline, target_instructions, 'assigned'
  ) returning id into assignment_key;

  update public.complaints
  set status = 'Assigned', deadline = target_deadline, updated_at = now()
  where id = target_complaint;

  insert into public.notifications (user_id, complaint_id, title, message)
  values (target_worker, target_complaint, 'New task assigned', 'A civic issue has been assigned to you.');

  insert into public.audit_logs (actor_id, action, entity_type, entity_id, details)
  values (
    auth.uid(), 'complaint.assigned', 'complaint', target_complaint,
    jsonb_build_object('worker_id', worker_row.id, 'deadline', target_deadline, 'assignment_id', assignment_key)
  );

  return assignment_key;
end;
$$;
