CREATE TABLE IF NOT EXISTS users (
  id text PRIMARY KEY,
  name text NOT NULL,
  email text NOT NULL UNIQUE,
  password_salt text NOT NULL,
  password_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS street text;
ALTER TABLE users ADD COLUMN IF NOT EXISTS postal_code text;
ALTER TABLE users ADD COLUMN IF NOT EXISTS city text;
ALTER TABLE users ADD COLUMN IF NOT EXISTS country text DEFAULT 'Deutschland';
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone text;

CREATE TABLE IF NOT EXISTS sessions (
  token_hash text PRIMARY KEY,
  user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS sessions_user_id_idx ON sessions(user_id);
CREATE INDEX IF NOT EXISTS sessions_expires_at_idx ON sessions(expires_at);

CREATE TABLE IF NOT EXISTS defect_cases (
  id text PRIMARY KEY,
  user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title text NOT NULL,
  category text NOT NULL DEFAULT 'Sonstiges',
  description text NOT NULL,
  property_label text,
  location_label text,
  discovered_on date,
  recipient_name text,
  recipient_email text,
  recipient_address text,
  deadline_on date,
  status text NOT NULL DEFAULT 'draft',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS defect_cases_user_id_idx ON defect_cases(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS case_events (
  id text PRIMARY KEY,
  case_id text NOT NULL REFERENCES defect_cases(id) ON DELETE CASCADE,
  user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  event_type text NOT NULL,
  note text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS case_events_case_id_idx ON case_events(case_id, created_at DESC);

CREATE TABLE IF NOT EXISTS attachments (
  id text PRIMARY KEY,
  case_id text NOT NULL REFERENCES defect_cases(id) ON DELETE CASCADE,
  user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  original_name text NOT NULL,
  stored_name text NOT NULL,
  mime_type text NOT NULL,
  size_bytes integer NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS attachments_case_id_idx ON attachments(case_id, created_at);


-- v0.3: Privat- und Hausverwaltungs-Arbeitsbereiche
CREATE TABLE IF NOT EXISTS organizations (
  id text PRIMARY KEY,
  name text NOT NULL,
  plan_code text NOT NULL DEFAULT 'business',
  created_by text NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS organization_memberships (
  organization_id text NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role text NOT NULL DEFAULT 'member',
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, user_id)
);
CREATE INDEX IF NOT EXISTS organization_memberships_user_idx ON organization_memberships(user_id);

ALTER TABLE defect_cases ADD COLUMN IF NOT EXISTS organization_id text REFERENCES organizations(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS defect_cases_org_idx ON defect_cases(organization_id, updated_at DESC);


-- v0.4: echte Objekt-/Einheitenstruktur für Hausverwaltungen
CREATE TABLE IF NOT EXISTS properties (
  id text PRIMARY KEY,
  organization_id text REFERENCES organizations(id) ON DELETE CASCADE,
  user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name text NOT NULL,
  street text,
  postal_code text,
  city text,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS properties_org_idx ON properties(organization_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS properties_user_idx ON properties(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS units (
  id text PRIMARY KEY,
  property_id text NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  label text NOT NULL,
  floor text,
  position_label text,
  area_sqm numeric,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS units_property_idx ON units(property_id, label);

CREATE TABLE IF NOT EXISTS contacts (
  id text PRIMARY KEY,
  organization_id text REFERENCES organizations(id) ON DELETE CASCADE,
  user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name text NOT NULL,
  email text,
  phone text,
  contact_type text NOT NULL DEFAULT 'tenant',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS contacts_org_idx ON contacts(organization_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS contacts_user_idx ON contacts(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS unit_contacts (
  unit_id text NOT NULL REFERENCES units(id) ON DELETE CASCADE,
  contact_id text NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
  role text NOT NULL DEFAULT 'tenant',
  is_primary boolean NOT NULL DEFAULT false,
  PRIMARY KEY (unit_id, contact_id)
);

ALTER TABLE defect_cases ADD COLUMN IF NOT EXISTS property_id text REFERENCES properties(id) ON DELETE SET NULL;
ALTER TABLE defect_cases ADD COLUMN IF NOT EXISTS unit_id text REFERENCES units(id) ON DELETE SET NULL;
ALTER TABLE defect_cases ADD COLUMN IF NOT EXISTS assigned_user_id text REFERENCES users(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS defect_cases_property_idx ON defect_cases(property_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS defect_cases_unit_idx ON defect_cases(unit_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS defect_cases_assignee_idx ON defect_cases(assigned_user_id, updated_at DESC);


-- v0.5: erweiterte Verwaltungs-Stammdaten
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS street text;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS postal_code text;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS city text;
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS notes text;
ALTER TABLE units ADD COLUMN IF NOT EXISTS notes text;

-- v0.6: digitale Mieter-Verknüpfungen
ALTER TABLE properties ADD COLUMN IF NOT EXISTS allow_tenant_submissions boolean NOT NULL DEFAULT true;
ALTER TABLE defect_cases ADD COLUMN IF NOT EXISTS tenant_link_id text;
ALTER TABLE defect_cases ADD COLUMN IF NOT EXISTS submitted_by_tenant boolean NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS tenant_invitations (
  id text PRIMARY KEY,
  token_hash text NOT NULL UNIQUE,
  organization_id text NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  property_id text NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  unit_id text NOT NULL REFERENCES units(id) ON DELETE CASCADE,
  contact_id text NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
  email text NOT NULL,
  created_by text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at timestamptz NOT NULL,
  accepted_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS tenant_invitations_email_idx ON tenant_invitations(lower(email), expires_at DESC);

CREATE TABLE IF NOT EXISTS tenant_links (
  id text PRIMARY KEY,
  organization_id text NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  property_id text NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  unit_id text NOT NULL REFERENCES units(id) ON DELETE CASCADE,
  contact_id text NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
  user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  status text NOT NULL DEFAULT 'active',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (unit_id, user_id)
);
CREATE INDEX IF NOT EXISTS tenant_links_user_idx ON tenant_links(user_id, status);
CREATE INDEX IF NOT EXISTS tenant_links_org_idx ON tenant_links(organization_id, status);

DO $$ BEGIN
  ALTER TABLE defect_cases ADD CONSTRAINT defect_cases_tenant_link_fk FOREIGN KEY (tenant_link_id) REFERENCES tenant_links(id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- v0.7: Kommunikation und Kontomails
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at timestamptz;
ALTER TABLE case_events ADD COLUMN IF NOT EXISTS visibility text NOT NULL DEFAULT 'shared';

CREATE TABLE IF NOT EXISTS email_verification_tokens (
  id text PRIMARY KEY,
  user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash text NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL,
  used_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS email_verification_user_idx ON email_verification_tokens(user_id, expires_at DESC);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
  id text PRIMARY KEY,
  user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash text NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL,
  used_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS password_reset_user_idx ON password_reset_tokens(user_id, expires_at DESC);

CREATE TABLE IF NOT EXISTS case_messages (
  id text PRIMARY KEY,
  case_id text NOT NULL REFERENCES defect_cases(id) ON DELETE CASCADE,
  user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  message text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS case_messages_case_idx ON case_messages(case_id, created_at);


-- v0.8: Dienstleister & Arbeitsaufträge
CREATE TABLE IF NOT EXISTS service_providers (
  id text PRIMARY KEY,
  organization_id text NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  company_name text NOT NULL,
  trade text NOT NULL DEFAULT 'Sonstiges',
  contact_name text,
  email text,
  phone text,
  street text,
  postal_code text,
  city text,
  notes text,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS service_providers_org_idx ON service_providers(organization_id, active, company_name);

CREATE TABLE IF NOT EXISTS work_orders (
  id text PRIMARY KEY,
  organization_id text NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  case_id text NOT NULL REFERENCES defect_cases(id) ON DELETE CASCADE,
  provider_id text NOT NULL REFERENCES service_providers(id) ON DELETE RESTRICT,
  created_by text NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  title text NOT NULL,
  description text NOT NULL,
  status text NOT NULL DEFAULT 'draft',
  due_on date,
  scheduled_for timestamptz,
  contractor_note text,
  token_hash text NOT NULL UNIQUE,
  token_expires_at timestamptz NOT NULL,
  sent_at timestamptz,
  accepted_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS work_orders_org_idx ON work_orders(organization_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS work_orders_case_idx ON work_orders(case_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS work_orders_provider_idx ON work_orders(provider_id, updated_at DESC);


-- v0.9: Benachrichtigungen, Audit-Log & Verwaltungsstatus
CREATE TABLE IF NOT EXISTS notifications (
  id text PRIMARY KEY,
  user_id text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  organization_id text REFERENCES organizations(id) ON DELETE CASCADE,
  case_id text REFERENCES defect_cases(id) ON DELETE CASCADE,
  type text NOT NULL,
  title text NOT NULL,
  body text,
  link text,
  read_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS notifications_user_idx ON notifications(user_id, read_at, created_at DESC);

CREATE TABLE IF NOT EXISTS audit_logs (
  id text PRIMARY KEY,
  organization_id text NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id text REFERENCES users(id) ON DELETE SET NULL,
  case_id text REFERENCES defect_cases(id) ON DELETE SET NULL,
  action text NOT NULL,
  entity_type text NOT NULL,
  entity_id text,
  summary text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS audit_logs_org_idx ON audit_logs(organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_logs_case_idx ON audit_logs(case_id, created_at DESC);


-- v0.10: Konto, Datenschutz und Team-Lifecycle
ALTER TABLE organization_memberships ADD COLUMN IF NOT EXISTS active boolean NOT NULL DEFAULT true;
ALTER TABLE organization_memberships ADD COLUMN IF NOT EXISTS deactivated_at timestamptz;
ALTER TABLE organization_memberships ADD COLUMN IF NOT EXISTS deactivated_by text REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE tenant_links ADD COLUMN IF NOT EXISTS disconnected_at timestamptz;
ALTER TABLE tenant_links ADD COLUMN IF NOT EXISTS disconnected_by text REFERENCES users(id) ON DELETE SET NULL;


-- v0.10: Tarife, Testphase, Limits und Abrechnungsgrundlage
ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_code text NOT NULL DEFAULT 'private_free';
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status text NOT NULL DEFAULT 'active';
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_provider text;
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_customer_id text;
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_id text;
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_current_period_end timestamptz;

ALTER TABLE organizations ADD COLUMN IF NOT EXISTS subscription_status text NOT NULL DEFAULT 'trialing';
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS trial_ends_at timestamptz;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS subscription_provider text;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS subscription_customer_id text;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS subscription_id text;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS subscription_current_period_end timestamptz;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS max_members integer NOT NULL DEFAULT 5;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS max_properties integer NOT NULL DEFAULT 25;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS max_units integer NOT NULL DEFAULT 250;

CREATE TABLE IF NOT EXISTS billing_events (
  id text PRIMARY KEY,
  provider text NOT NULL,
  provider_event_id text UNIQUE,
  organization_id text REFERENCES organizations(id) ON DELETE SET NULL,
  user_id text REFERENCES users(id) ON DELETE SET NULL,
  event_type text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS billing_events_org_idx ON billing_events(organization_id,created_at DESC);


-- v0.11: Aufgaben, Wiedervorlagen und Eskalationen
CREATE TABLE IF NOT EXISTS case_tasks (
  id text PRIMARY KEY,
  organization_id text REFERENCES organizations(id) ON DELETE CASCADE,
  case_id text NOT NULL REFERENCES defect_cases(id) ON DELETE CASCADE,
  created_by text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  assigned_user_id text REFERENCES users(id) ON DELETE SET NULL,
  title text NOT NULL,
  description text,
  priority text NOT NULL DEFAULT 'normal',
  status text NOT NULL DEFAULT 'open',
  due_at timestamptz,
  remind_at timestamptz,
  reminder_sent_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS case_tasks_org_idx ON case_tasks(organization_id,status,due_at);
CREATE INDEX IF NOT EXISTS case_tasks_assignee_idx ON case_tasks(assigned_user_id,status,due_at);
CREATE INDEX IF NOT EXISTS case_tasks_case_idx ON case_tasks(case_id,created_at DESC);


-- v0.12: Kalender und Terminplanung
CREATE TABLE IF NOT EXISTS calendar_events (
  id text PRIMARY KEY,
  organization_id text REFERENCES organizations(id) ON DELETE CASCADE,
  case_id text REFERENCES defect_cases(id) ON DELETE CASCADE,
  property_id text REFERENCES properties(id) ON DELETE SET NULL,
  unit_id text REFERENCES units(id) ON DELETE SET NULL,
  created_by text NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  assigned_user_id text REFERENCES users(id) ON DELETE SET NULL,
  event_type text NOT NULL DEFAULT 'internal',
  title text NOT NULL,
  notes text,
  starts_at timestamptz NOT NULL,
  ends_at timestamptz NOT NULL,
  status text NOT NULL DEFAULT 'planned',
  notify_tenant boolean NOT NULL DEFAULT false,
  reminder_at timestamptz,
  reminder_sent_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS calendar_events_org_idx ON calendar_events(organization_id,starts_at);
CREATE INDEX IF NOT EXISTS calendar_events_user_idx ON calendar_events(assigned_user_id,starts_at);
CREATE INDEX IF NOT EXISTS calendar_events_case_idx ON calendar_events(case_id,starts_at);
