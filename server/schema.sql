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
