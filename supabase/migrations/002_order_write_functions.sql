-- 002: write orders and order_changes in one transaction.
-- PostgREST runs each RPC call in a single transaction, so the backend never writes
-- orders directly: it calls create_order / update_order, which always add the matching
-- order_changes rows.

-- Object path of the proof clip in the "audio" bucket (calls.audio_url is also a bucket path).
alter table order_changes add column clip_path text;

-- New order + its 'created' change row. p_fields: {item, spec, quantity, unit, rate, delivery_date}.
create or replace function create_order(
  p_client_id   bigint,
  p_fields      jsonb,
  p_call_id     bigint default null,
  p_clip_start  numeric default null,
  p_clip_end    numeric default null,
  p_clip_path   text default null,
  p_confidence  real default null
) returns bigint
language plpgsql
as $$
declare
  v_id bigint;
begin
  insert into orders (client_id, item, spec, quantity, unit, rate, delivery_date)
  values (
    p_client_id,
    p_fields ->> 'item',
    p_fields ->> 'spec',
    (p_fields ->> 'quantity')::numeric,
    p_fields ->> 'unit',
    (p_fields ->> 'rate')::numeric,
    (p_fields ->> 'delivery_date')::date
  )
  returning id into v_id;

  insert into order_changes (order_id, call_id, field, old_value, new_value,
                             clip_start, clip_end, clip_path, confidence)
  values (v_id, p_call_id, 'created', null, p_fields::text,
          p_clip_start, p_clip_end, p_clip_path, p_confidence);
  return v_id;
end;
$$;

-- Update some fields of an order. One order_changes row per field that actually changed.
-- Returns the number of changed fields.
create or replace function update_order(
  p_order_id    bigint,
  p_fields      jsonb,
  p_call_id     bigint default null,
  p_clip_start  numeric default null,
  p_clip_end    numeric default null,
  p_clip_path   text default null,
  p_confidence  real default null
) returns integer
language plpgsql
as $$
declare
  v_old   jsonb;
  v_key   text;
  v_type  text;
  v_same  boolean;
  v_count integer := 0;
begin
  select to_jsonb(o) into v_old from orders o where o.id = p_order_id for update;
  if v_old is null then
    raise exception 'order % not found', p_order_id;
  end if;

  for v_key in select jsonb_object_keys(p_fields) loop
    v_type := case v_key
      when 'quantity' then 'numeric'
      when 'rate' then 'numeric'
      when 'delivery_date' then 'date'
      when 'item' then 'text'
      when 'spec' then 'text'
      when 'unit' then 'text'
      when 'status' then 'text'
    end;
    if v_type is null then
      raise exception 'field % cannot be updated', v_key;
    end if;

    execute format('select %I is not distinct from $1::%s from orders where id = $2', v_key, v_type)
      into v_same using p_fields ->> v_key, p_order_id;
    continue when v_same;

    execute format('update orders set %I = $1::%s, updated_at = now() where id = $2', v_key, v_type)
      using p_fields ->> v_key, p_order_id;
    insert into order_changes (order_id, call_id, field, old_value, new_value,
                               clip_start, clip_end, clip_path, confidence)
    values (p_order_id, p_call_id, v_key, v_old ->> v_key, p_fields ->> v_key,
            p_clip_start, p_clip_end, p_clip_path, p_confidence);
    v_count := v_count + 1;
  end loop;
  return v_count;
end;
$$;

-- Service key only, like the tables.
revoke execute on function create_order(bigint, jsonb, bigint, numeric, numeric, text, real) from public, anon, authenticated;
revoke execute on function update_order(bigint, jsonb, bigint, numeric, numeric, text, real) from public, anon, authenticated;
