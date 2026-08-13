import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';
import express from 'express';
import helmet from 'helmet';
import cookieParser from 'cookie-parser';
import multer from 'multer';
import PDFDocument from 'pdfkit';
import pg from 'pg';

const { Pool } = pg;
const scrypt = promisify(crypto.scrypt);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(__dirname, '..');
const publicDir = path.join(appRoot, 'public');
const uploadDir = process.env.UPLOAD_DIR || '/data/uploads';
const port = Number(process.env.PORT || 3000);
const cookieName = process.env.SESSION_COOKIE_NAME || 'maengelfix_session';
const production = process.env.NODE_ENV === 'production';

fs.mkdirSync(uploadDir, { recursive: true });

const pool = new Pool({ connectionString: process.env.DATABASE_URL });
const schema = fs.readFileSync(path.join(__dirname, 'schema.sql'), 'utf8');
await pool.query(schema);
await pool.query('DELETE FROM sessions WHERE expires_at <= now()');

const app = express();
app.set('trust proxy', 1);
app.use(helmet({ crossOriginResourcePolicy: { policy: 'same-origin' } }));
app.use(express.json({ limit: '1mb' }));
app.use(cookieParser());

function id() {
  return crypto.randomUUID();
}

function tokenHash(token) {
  return crypto.createHash('sha256').update(token).digest('hex');
}

async function makePassword(password) {
  const salt = crypto.randomBytes(16).toString('hex');
  const derived = await scrypt(password, salt, 64);
  return { salt, hash: Buffer.from(derived).toString('hex') };
}

async function verifyPassword(password, salt, expectedHex) {
  const derived = Buffer.from(await scrypt(password, salt, 64));
  const expected = Buffer.from(expectedHex, 'hex');
  return expected.length === derived.length && crypto.timingSafeEqual(expected, derived);
}

function cleanText(value, max = 1000) {
  if (value === null || value === undefined) return null;
  return String(value).trim().slice(0, max);
}

function publicUser(row) {
  return {
    id: row.id,
    name: row.name,
    email: row.email,
    street: row.street || '',
    postalCode: row.postal_code || '',
    city: row.city || '',
    country: row.country || 'Deutschland',
    phone: row.phone || ''
  };
}

function setSessionCookie(res, token) {
  res.cookie(cookieName, token, {
    httpOnly: true,
    secure: production,
    sameSite: 'lax',
    path: '/',
    maxAge: 30 * 24 * 60 * 60 * 1000
  });
}

async function createSession(userId, res) {
  const token = crypto.randomBytes(32).toString('base64url');
  await pool.query(
    `INSERT INTO sessions (token_hash, user_id, expires_at)
     VALUES ($1, $2, now() + interval '30 days')`,
    [tokenHash(token), userId]
  );
  setSessionCookie(res, token);
}

async function auth(req, res, next) {
  try {
    const token = req.cookies[cookieName];
    if (!token) return res.status(401).json({ error: 'Bitte melde dich an.' });
    const result = await pool.query(
      `SELECT u.id, u.name, u.email, u.street, u.postal_code, u.city, u.country, u.phone
       FROM sessions s
       JOIN users u ON u.id = s.user_id
       WHERE s.token_hash = $1 AND s.expires_at > now()`,
      [tokenHash(token)]
    );
    if (!result.rowCount) {
      res.clearCookie(cookieName, { path: '/' });
      return res.status(401).json({ error: 'Deine Anmeldung ist abgelaufen.' });
    }
    req.user = result.rows[0];
    next();
  } catch (error) {
    next(error);
  }
}

const allowedStatuses = new Set(['draft', 'sent', 'reply', 'in_progress', 'resolved']);


async function organizationForUser(userId) {
  const result = await pool.query(
    `SELECT o.id, o.name, o.plan_code, om.role
     FROM organization_memberships om
     JOIN organizations o ON o.id = om.organization_id
     WHERE om.user_id = $1
     ORDER BY om.created_at
     LIMIT 1`,
    [userId]
  );
  return result.rows[0] || null;
}

async function canAccessCase(userId, caseId) {
  const result = await pool.query(
    `SELECT c.*
     FROM defect_cases c
     WHERE c.id = $1 AND (
       c.user_id = $2 OR
       (c.organization_id IS NOT NULL AND EXISTS (
         SELECT 1 FROM organization_memberships om
         WHERE om.organization_id = c.organization_id AND om.user_id = $2
       ))
     )`,
    [caseId, userId]
  );
  return result.rows[0] || null;
}

app.get('/api/health', async (_req, res) => {
  await pool.query('SELECT 1');
  res.json({ ok: true, service: 'maengelfix', version: '0.5.0' });
});

app.post('/api/auth/register', async (req, res, next) => {
  try {
    const name = cleanText(req.body.name, 120);
    const email = cleanText(req.body.email, 254)?.toLowerCase();
    const password = String(req.body.password || '');
    if (!name || !email || !email.includes('@') || password.length < 8) {
      return res.status(400).json({ error: 'Name, gültige E-Mail und mindestens 8 Zeichen Passwort sind erforderlich.' });
    }
    const existing = await pool.query('SELECT 1 FROM users WHERE email = $1', [email]);
    if (existing.rowCount) return res.status(409).json({ error: 'Für diese E-Mail existiert bereits ein Konto.' });

    const credentials = await makePassword(password);
    const userId = id();
    const result = await pool.query(
      `INSERT INTO users (id, name, email, password_salt, password_hash, country)
       VALUES ($1,$2,$3,$4,$5,'Deutschland')
       RETURNING id, name, email, street, postal_code, city, country, phone`,
      [userId, name, email, credentials.salt, credentials.hash]
    );
    await createSession(userId, res);
    res.status(201).json({ user: publicUser(result.rows[0]) });
  } catch (error) {
    next(error);
  }
});

app.post('/api/auth/login', async (req, res, next) => {
  try {
    const email = cleanText(req.body.email, 254)?.toLowerCase();
    const password = String(req.body.password || '');
    const result = await pool.query(
      `SELECT id, name, email, password_salt, password_hash, street, postal_code, city, country, phone
       FROM users WHERE email = $1`,
      [email]
    );
    const row = result.rows[0];
    if (!row || !(await verifyPassword(password, row.password_salt, row.password_hash))) {
      return res.status(401).json({ error: 'E-Mail oder Passwort ist nicht korrekt.' });
    }
    await createSession(row.id, res);
    res.json({ user: publicUser(row) });
  } catch (error) {
    next(error);
  }
});

app.post('/api/auth/logout', auth, async (req, res, next) => {
  try {
    const token = req.cookies[cookieName];
    if (token) await pool.query('DELETE FROM sessions WHERE token_hash = $1', [tokenHash(token)]);
    res.clearCookie(cookieName, { path: '/' });
    res.status(204).end();
  } catch (error) {
    next(error);
  }
});

app.get('/api/me', auth, (req, res) => res.json({ user: publicUser(req.user) }));

app.patch('/api/profile', auth, async (req, res, next) => {
  try {
    const name = cleanText(req.body.name, 120);
    if (!name) return res.status(400).json({ error: 'Bitte gib deinen Namen an.' });
    const result = await pool.query(
      `UPDATE users SET
        name=$2,
        street=$3,
        postal_code=$4,
        city=$5,
        country=$6,
        phone=$7
       WHERE id=$1
       RETURNING id, name, email, street, postal_code, city, country, phone`,
      [
        req.user.id,
        name,
        cleanText(req.body.street, 180),
        cleanText(req.body.postalCode, 20),
        cleanText(req.body.city, 120),
        cleanText(req.body.country, 80) || 'Deutschland',
        cleanText(req.body.phone, 60)
      ]
    );
    res.json({ user: publicUser(result.rows[0]) });
  } catch (error) {
    next(error);
  }
});


app.get('/api/team', auth, async (req, res, next) => {
  try {
    const organization = await organizationForUser(req.user.id);
    if (!organization) return res.json({ organization: null, members: [] });
    const members = await pool.query(
      `SELECT u.id, u.name, u.email, om.role, om.created_at
       FROM organization_memberships om
       JOIN users u ON u.id = om.user_id
       WHERE om.organization_id = $1
       ORDER BY CASE om.role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END, u.name`,
      [organization.id]
    );
    res.json({ organization, members: members.rows });
  } catch (error) {
    next(error);
  }
});

app.post('/api/team', auth, async (req, res, next) => {
  try {
    const existing = await organizationForUser(req.user.id);
    if (existing) return res.status(409).json({ error: 'Du gehörst bereits zu einem Hausverwaltungs-Arbeitsbereich.' });
    const name = cleanText(req.body.name, 180);
    if (!name) return res.status(400).json({ error: 'Bitte gib den Namen der Hausverwaltung an.' });
    const orgId = id();
    await pool.query('BEGIN');
    try {
      await pool.query(
        `INSERT INTO organizations (id, name, plan_code, created_by) VALUES ($1,$2,'business',$3)`,
        [orgId, name, req.user.id]
      );
      await pool.query(
        `INSERT INTO organization_memberships (organization_id, user_id, role) VALUES ($1,$2,'owner')`,
        [orgId, req.user.id]
      );
      await pool.query('COMMIT');
    } catch (error) {
      await pool.query('ROLLBACK');
      throw error;
    }
    res.status(201).json({ organization: { id: orgId, name, plan_code: 'business', role: 'owner' } });
  } catch (error) {
    next(error);
  }
});

app.post('/api/team/members', auth, async (req, res, next) => {
  try {
    const organization = await organizationForUser(req.user.id);
    if (!organization || !['owner', 'admin'].includes(organization.role)) {
      return res.status(403).json({ error: 'Nur Inhaber und Admins können Mitarbeiterkonten anlegen.' });
    }
    const name = cleanText(req.body.name, 120);
    const email = cleanText(req.body.email, 254)?.toLowerCase();
    const password = String(req.body.password || '');
    const role = req.body.role === 'admin' ? 'admin' : 'member';
    if (!name || !email || !email.includes('@') || password.length < 8) {
      return res.status(400).json({ error: 'Name, gültige E-Mail und ein Startpasswort mit mindestens 8 Zeichen sind erforderlich.' });
    }
    const existing = await pool.query('SELECT id FROM users WHERE email=$1', [email]);
    if (existing.rowCount) return res.status(409).json({ error: 'Für diese E-Mail existiert bereits ein MängelFix-Konto.' });
    const credentials = await makePassword(password);
    const userId = id();
    await pool.query('BEGIN');
    try {
      await pool.query(
        `INSERT INTO users (id,name,email,password_salt,password_hash,country) VALUES ($1,$2,$3,$4,$5,'Deutschland')`,
        [userId, name, email, credentials.salt, credentials.hash]
      );
      await pool.query(
        `INSERT INTO organization_memberships (organization_id,user_id,role) VALUES ($1,$2,$3)`,
        [organization.id, userId, role]
      );
      await pool.query('COMMIT');
    } catch (error) {
      await pool.query('ROLLBACK');
      throw error;
    }
    res.status(201).json({ member: { id: userId, name, email, role } });
  } catch (error) {
    next(error);
  }
});



async function scopeForUser(userId) {
  const organization = await organizationForUser(userId);
  return { organization, organizationId: organization?.id || null };
}


app.get('/api/management/overview', auth, async (req, res, next) => {
  try {
    const organization = await organizationForUser(req.user.id);
    if (!organization) return res.json({ organization: null });
    const [propertyCount, unitCount, contactCount, cases, members] = await Promise.all([
      pool.query('SELECT count(*)::int AS count FROM properties WHERE organization_id=$1', [organization.id]),
      pool.query('SELECT count(*)::int AS count FROM units u JOIN properties p ON p.id=u.property_id WHERE p.organization_id=$1', [organization.id]),
      pool.query('SELECT count(*)::int AS count FROM contacts WHERE organization_id=$1', [organization.id]),
      pool.query(`SELECT c.id,c.title,c.status,c.deadline_on,c.assigned_user_id,p.name AS property_name,u.label AS unit_label,au.name AS assigned_user_name
        FROM defect_cases c LEFT JOIN properties p ON p.id=c.property_id LEFT JOIN units u ON u.id=c.unit_id LEFT JOIN users au ON au.id=c.assigned_user_id
        WHERE c.organization_id=$1 ORDER BY c.updated_at DESC`, [organization.id]),
      pool.query(`SELECT usr.id,usr.name,om.role,
        (SELECT count(*)::int FROM defect_cases c WHERE c.organization_id=$1 AND c.assigned_user_id=usr.id AND c.status<>'resolved') AS open_cases
        FROM organization_memberships om JOIN users usr ON usr.id=om.user_id WHERE om.organization_id=$1 ORDER BY usr.name`, [organization.id])
    ]);
    const rows = cases.rows;
    const now = new Date(); now.setHours(0,0,0,0);
    const overdue = rows.filter(c => c.deadline_on && c.status !== 'resolved' && new Date(c.deadline_on) < now).length;
    res.json({ organization, metrics: {
      properties: propertyCount.rows[0].count, units: unitCount.rows[0].count, contacts: contactCount.rows[0].count,
      open: rows.filter(c=>c.status!=='resolved').length, unassigned: rows.filter(c=>c.status!=='resolved'&&!c.assigned_user_id).length, overdue
    }, recent: rows.slice(0,6), members: members.rows });
  } catch (error) { next(error); }
});

app.get('/api/management/options', auth, async (req, res, next) => {
  try {
    const organization = await organizationForUser(req.user.id);
    if (!organization) return res.json({ organization: null, properties: [], members: [] });
    const [properties, members] = await Promise.all([
      pool.query(`SELECT p.id,p.name,p.street,p.postal_code,p.city,
        COALESCE(json_agg(json_build_object('id',u.id,'label',u.label,'floor',u.floor,'positionLabel',u.position_label) ORDER BY u.label) FILTER (WHERE u.id IS NOT NULL),'[]') AS units
        FROM properties p LEFT JOIN units u ON u.property_id=p.id WHERE p.organization_id=$1 GROUP BY p.id ORDER BY p.name`, [organization.id]),
      pool.query(`SELECT u.id,u.name,om.role FROM organization_memberships om JOIN users u ON u.id=om.user_id WHERE om.organization_id=$1 ORDER BY u.name`, [organization.id])
    ]);
    res.json({ organization, properties: properties.rows, members: members.rows });
  } catch (error) { next(error); }
});

app.get('/api/properties', auth, async (req, res, next) => {
  try {
    const { organizationId } = await scopeForUser(req.user.id);
    const result = await pool.query(
      `SELECT p.*,
        (SELECT count(*)::int FROM units u WHERE u.property_id=p.id) AS unit_count,
        (SELECT count(*)::int FROM defect_cases c WHERE c.property_id=p.id AND c.status <> 'resolved') AS open_case_count
       FROM properties p
       WHERE ($2::text IS NOT NULL AND p.organization_id=$2) OR ($2::text IS NULL AND p.organization_id IS NULL AND p.user_id=$1)
       ORDER BY p.name`,
      [req.user.id, organizationId]
    );
    res.json({ properties: result.rows });
  } catch (error) { next(error); }
});

app.post('/api/properties', auth, async (req, res, next) => {
  try {
    const name = cleanText(req.body.name, 180);
    if (!name) return res.status(400).json({ error: 'Bitte gib einen Objektnamen an.' });
    const { organizationId } = await scopeForUser(req.user.id);
    const propertyId = id();
    const result = await pool.query(
      `INSERT INTO properties (id,organization_id,user_id,name,street,postal_code,city,notes)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *`,
      [propertyId, organizationId, req.user.id, name, cleanText(req.body.street,180), cleanText(req.body.postalCode,20), cleanText(req.body.city,120), cleanText(req.body.notes,2000)]
    );
    res.status(201).json({ property: result.rows[0] });
  } catch (error) { next(error); }
});

app.get('/api/properties/:propertyId', auth, async (req, res, next) => {
  try {
    const { organizationId } = await scopeForUser(req.user.id);
    const property = await pool.query(
      `SELECT * FROM properties WHERE id=$1 AND (($3::text IS NOT NULL AND organization_id=$3) OR ($3::text IS NULL AND organization_id IS NULL AND user_id=$2))`,
      [req.params.propertyId, req.user.id, organizationId]
    );
    if (!property.rowCount) return res.status(404).json({ error: 'Objekt nicht gefunden.' });
    const [units, cases] = await Promise.all([
      pool.query(`SELECT u.*,
          (SELECT count(*)::int FROM unit_contacts uc WHERE uc.unit_id=u.id) AS contact_count,
          (SELECT count(*)::int FROM defect_cases c WHERE c.unit_id=u.id AND c.status <> 'resolved') AS open_case_count
        FROM units u WHERE u.property_id=$1 ORDER BY u.label`, [req.params.propertyId]),
      pool.query(`SELECT c.*, u.name AS assigned_user_name FROM defect_cases c LEFT JOIN users u ON u.id=c.assigned_user_id WHERE c.property_id=$1 ORDER BY c.updated_at DESC`, [req.params.propertyId])
    ]);
    res.json({ property: property.rows[0], units: units.rows, cases: cases.rows });
  } catch (error) { next(error); }
});

app.post('/api/properties/:propertyId/units', auth, async (req, res, next) => {
  try {
    const { organizationId } = await scopeForUser(req.user.id);
    const property = await pool.query(`SELECT 1 FROM properties WHERE id=$1 AND (($3::text IS NOT NULL AND organization_id=$3) OR ($3::text IS NULL AND organization_id IS NULL AND user_id=$2))`, [req.params.propertyId, req.user.id, organizationId]);
    if (!property.rowCount) return res.status(404).json({ error: 'Objekt nicht gefunden.' });
    const label = cleanText(req.body.label,120);
    if (!label) return res.status(400).json({ error: 'Bitte gib eine Bezeichnung für die Einheit an.' });
    const result = await pool.query(
      `INSERT INTO units (id,property_id,label,floor,position_label,area_sqm) VALUES ($1,$2,$3,$4,$5,$6) RETURNING *`,
      [id(), req.params.propertyId, label, cleanText(req.body.floor,60), cleanText(req.body.positionLabel,120), req.body.areaSqm ? Number(req.body.areaSqm) : null]
    );
    res.status(201).json({ unit: result.rows[0] });
  } catch (error) { next(error); }
});


app.get('/api/units/:unitId', auth, async (req, res, next) => {
  try {
    const { organizationId } = await scopeForUser(req.user.id);
    const unit = await pool.query(`SELECT u.*,p.name AS property_name,p.street AS property_street,p.postal_code AS property_postal_code,p.city AS property_city
      FROM units u JOIN properties p ON p.id=u.property_id WHERE u.id=$1 AND (($3::text IS NOT NULL AND p.organization_id=$3) OR ($3::text IS NULL AND p.organization_id IS NULL AND p.user_id=$2))`, [req.params.unitId, req.user.id, organizationId]);
    if (!unit.rowCount) return res.status(404).json({ error: 'Einheit nicht gefunden.' });
    const [contacts,cases] = await Promise.all([
      pool.query(`SELECT c.*,uc.role,uc.is_primary FROM unit_contacts uc JOIN contacts c ON c.id=uc.contact_id WHERE uc.unit_id=$1 ORDER BY uc.is_primary DESC,c.name`, [req.params.unitId]),
      pool.query(`SELECT c.*,au.name AS assigned_user_name FROM defect_cases c LEFT JOIN users au ON au.id=c.assigned_user_id WHERE c.unit_id=$1 ORDER BY c.updated_at DESC`, [req.params.unitId])
    ]);
    res.json({ unit: unit.rows[0], contacts: contacts.rows, cases: cases.rows });
  } catch (error) { next(error); }
});

app.delete('/api/units/:unitId/contacts/:contactId', auth, async (req,res,next)=>{
  try {
    const { organizationId } = await scopeForUser(req.user.id);
    const allowed = await pool.query(`SELECT 1 FROM units u JOIN properties p ON p.id=u.property_id WHERE u.id=$1 AND (($3::text IS NOT NULL AND p.organization_id=$3) OR ($3::text IS NULL AND p.organization_id IS NULL AND p.user_id=$2))`, [req.params.unitId, req.user.id, organizationId]);
    if (!allowed.rowCount) return res.status(404).json({error:'Einheit nicht gefunden.'});
    await pool.query('DELETE FROM unit_contacts WHERE unit_id=$1 AND contact_id=$2',[req.params.unitId,req.params.contactId]);
    res.status(204).end();
  } catch(error){ next(error); }
});

app.get('/api/contacts', auth, async (req, res, next) => {
  try {
    const { organizationId } = await scopeForUser(req.user.id);
    const result = await pool.query(
      `SELECT * FROM contacts WHERE ($2::text IS NOT NULL AND organization_id=$2) OR ($2::text IS NULL AND organization_id IS NULL AND user_id=$1) ORDER BY name`,
      [req.user.id, organizationId]
    );
    res.json({ contacts: result.rows });
  } catch (error) { next(error); }
});

app.post('/api/contacts', auth, async (req, res, next) => {
  try {
    const name = cleanText(req.body.name,160);
    if (!name) return res.status(400).json({ error: 'Bitte gib einen Namen an.' });
    const { organizationId } = await scopeForUser(req.user.id);
    const result = await pool.query(
      `INSERT INTO contacts (id,organization_id,user_id,name,email,phone,contact_type,street,postal_code,city,notes) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) RETURNING *`,
      [id(), organizationId, req.user.id, name, cleanText(req.body.email,254)?.toLowerCase(), cleanText(req.body.phone,60), cleanText(req.body.contactType,40) || 'tenant', cleanText(req.body.street,180), cleanText(req.body.postalCode,20), cleanText(req.body.city,120), cleanText(req.body.notes,1200)]
    );
    res.status(201).json({ contact: result.rows[0] });
  } catch (error) { next(error); }
});

app.post('/api/units/:unitId/contacts', auth, async (req, res, next) => {
  try {
    const { organizationId } = await scopeForUser(req.user.id);
    const unit = await pool.query(`SELECT u.id FROM units u JOIN properties p ON p.id=u.property_id WHERE u.id=$1 AND (($3::text IS NOT NULL AND p.organization_id=$3) OR ($3::text IS NULL AND p.organization_id IS NULL AND p.user_id=$2))`, [req.params.unitId, req.user.id, organizationId]);
    if (!unit.rowCount) return res.status(404).json({ error: 'Einheit nicht gefunden.' });
    const contact = await pool.query(`SELECT id FROM contacts WHERE id=$1 AND (($3::text IS NOT NULL AND organization_id=$3) OR ($3::text IS NULL AND organization_id IS NULL AND user_id=$2))`, [req.body.contactId, req.user.id, organizationId]);
    if (!contact.rowCount) return res.status(404).json({ error: 'Kontakt nicht gefunden.' });
    await pool.query(`INSERT INTO unit_contacts (unit_id,contact_id,role,is_primary) VALUES ($1,$2,$3,$4) ON CONFLICT (unit_id,contact_id) DO UPDATE SET role=EXCLUDED.role,is_primary=EXCLUDED.is_primary`, [req.params.unitId, req.body.contactId, cleanText(req.body.role,40) || 'tenant', Boolean(req.body.isPrimary)]);
    res.status(204).end();
  } catch (error) { next(error); }
});

app.patch('/api/cases/:caseId/assignment', auth, async (req, res, next) => {
  try {
    const accessible = await canAccessCase(req.user.id, req.params.caseId);
    if (!accessible) return res.status(404).json({ error: 'Mangel nicht gefunden.' });
    const organization = await organizationForUser(req.user.id);
    if (!organization) return res.status(403).json({ error: 'Zuweisungen sind nur im Verwaltungs-Arbeitsbereich verfügbar.' });
    const propertyId = cleanText(req.body.propertyId,80) || null;
    const unitId = cleanText(req.body.unitId,80) || null;
    const assignedUserId = cleanText(req.body.assignedUserId,80) || null;
    if (propertyId) {
      const p = await pool.query('SELECT 1 FROM properties WHERE id=$1 AND organization_id=$2',[propertyId,organization.id]);
      if (!p.rowCount) return res.status(400).json({error:'Objekt gehört nicht zu dieser Verwaltung.'});
    }
    if (unitId) {
      const u = await pool.query('SELECT 1 FROM units u JOIN properties p ON p.id=u.property_id WHERE u.id=$1 AND p.organization_id=$2 AND ($3::text IS NULL OR p.id=$3)',[unitId,organization.id,propertyId]);
      if (!u.rowCount) return res.status(400).json({error:'Einheit gehört nicht zum gewählten Objekt.'});
    }
    if (assignedUserId) {
      const m = await pool.query('SELECT 1 FROM organization_memberships WHERE organization_id=$1 AND user_id=$2',[organization.id,assignedUserId]);
      if (!m.rowCount) return res.status(400).json({error:'Mitarbeiter gehört nicht zu dieser Verwaltung.'});
    }
    const result = await pool.query(`UPDATE defect_cases SET property_id=$2, unit_id=$3, assigned_user_id=$4,
      property_label=COALESCE((SELECT name FROM properties WHERE id=$2),property_label),
      location_label=COALESCE((SELECT label FROM units WHERE id=$3),location_label), updated_at=now() WHERE id=$1 RETURNING *`, [req.params.caseId, propertyId, unitId, assignedUserId]);
    await pool.query('INSERT INTO case_events (id,case_id,user_id,event_type,note) VALUES ($1,$2,$3,$4,$5)',[id(),req.params.caseId,req.user.id,'assignment','Objekt, Einheit oder Zuständigkeit wurde aktualisiert.']);
    res.json({ case: result.rows[0] });
  } catch (error) { next(error); }
});

app.get('/api/cases', auth, async (req, res, next) => {
  try {
    const result = await pool.query(
      `SELECT c.*, p.name AS property_name, un.label AS unit_name, au.name AS assigned_user_name,
        (SELECT count(*)::int FROM attachments a WHERE a.case_id = c.id) AS attachment_count
       FROM defect_cases c LEFT JOIN properties p ON p.id=c.property_id LEFT JOIN units un ON un.id=c.unit_id LEFT JOIN users au ON au.id=c.assigned_user_id
       WHERE c.user_id = $1 OR (
         c.organization_id IS NOT NULL AND EXISTS (
           SELECT 1 FROM organization_memberships om
           WHERE om.organization_id = c.organization_id AND om.user_id = $1
         )
       )
       ORDER BY c.updated_at DESC`,
      [req.user.id]
    );
    res.json({ cases: result.rows });
  } catch (error) {
    next(error);
  }
});

app.post('/api/cases', auth, async (req, res, next) => {
  const client = await pool.connect();
  try {
    const title = cleanText(req.body.title, 160);
    const description = cleanText(req.body.description, 6000);
    if (!title || !description) return res.status(400).json({ error: 'Titel und Beschreibung sind erforderlich.' });

    const caseId = id();
    await client.query('BEGIN');
    const result = await client.query(
      `INSERT INTO defect_cases
       (id,user_id,organization_id,title,category,description,property_label,location_label,discovered_on,recipient_name,recipient_email,recipient_address,deadline_on,status)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,'draft')
       RETURNING *`,
      [
        caseId,
        req.user.id,
        (await organizationForUser(req.user.id))?.id || null,
        title,
        cleanText(req.body.category, 80) || 'Sonstiges',
        description,
        cleanText(req.body.propertyLabel, 200),
        cleanText(req.body.locationLabel, 120),
        req.body.discoveredOn || null,
        cleanText(req.body.recipientName, 160),
        cleanText(req.body.recipientEmail, 254)?.toLowerCase(),
        cleanText(req.body.recipientAddress, 500),
        req.body.deadlineOn || null
      ]
    );
    await client.query(
      'INSERT INTO case_events (id, case_id, user_id, event_type, note) VALUES ($1,$2,$3,$4,$5)',
      [id(), caseId, req.user.id, 'created', 'Mangel wurde erfasst.']
    );
    await client.query('COMMIT');
    res.status(201).json({ case: result.rows[0] });
  } catch (error) {
    await client.query('ROLLBACK');
    next(error);
  } finally {
    client.release();
  }
});

app.get('/api/cases/:caseId', auth, async (req, res, next) => {
  try {
    const accessible = await canAccessCase(req.user.id, req.params.caseId);
    const result = { rowCount: accessible ? 1 : 0, rows: accessible ? [accessible] : [] };
    if (!result.rowCount) return res.status(404).json({ error: 'Mangel nicht gefunden.' });
    const [events, attachments] = await Promise.all([
      pool.query('SELECT e.*, u.name AS actor_name FROM case_events e LEFT JOIN users u ON u.id=e.user_id WHERE e.case_id = $1 ORDER BY e.created_at DESC', [req.params.caseId]),
      pool.query('SELECT id, original_name, mime_type, size_bytes, created_at FROM attachments WHERE case_id = $1 ORDER BY created_at', [req.params.caseId])
    ]);
    res.json({ case: result.rows[0], events: events.rows, attachments: attachments.rows });
  } catch (error) {
    next(error);
  }
});

app.patch('/api/cases/:caseId', auth, async (req, res, next) => {
  try {
    const status = cleanText(req.body.status, 40);
    if (status && !allowedStatuses.has(status)) return res.status(400).json({ error: 'Ungültiger Status.' });
    const accessible = await canAccessCase(req.user.id, req.params.caseId);
    const current = { rowCount: accessible ? 1 : 0, rows: accessible ? [accessible] : [] };
    if (!current.rowCount) return res.status(404).json({ error: 'Mangel nicht gefunden.' });
    const old = current.rows[0];
    const nextStatus = status || old.status;
    const result = await pool.query(
      `UPDATE defect_cases SET
       title=$3, category=$4, description=$5, property_label=$6, location_label=$7,
       discovered_on=$8, recipient_name=$9, recipient_email=$10, recipient_address=$11,
       deadline_on=$12, status=$13, updated_at=now()
       WHERE id=$1 RETURNING *`,
      [
        req.params.caseId,
        req.user.id,
        cleanText(req.body.title ?? old.title, 160),
        cleanText(req.body.category ?? old.category, 80),
        cleanText(req.body.description ?? old.description, 6000),
        cleanText(req.body.propertyLabel ?? old.property_label, 200),
        cleanText(req.body.locationLabel ?? old.location_label, 120),
        req.body.discoveredOn ?? old.discovered_on,
        cleanText(req.body.recipientName ?? old.recipient_name, 160),
        cleanText(req.body.recipientEmail ?? old.recipient_email, 254)?.toLowerCase(),
        cleanText(req.body.recipientAddress ?? old.recipient_address, 500),
        req.body.deadlineOn ?? old.deadline_on,
        nextStatus
      ]
    );
    if (nextStatus !== old.status) {
      await pool.query(
        'INSERT INTO case_events (id, case_id, user_id, event_type, note) VALUES ($1,$2,$3,$4,$5)',
        [id(), req.params.caseId, req.user.id, 'status', `Status geändert: ${nextStatus}`]
      );
    }
    res.json({ case: result.rows[0] });
  } catch (error) {
    next(error);
  }
});

app.post('/api/cases/:caseId/events', auth, async (req, res, next) => {
  try {
    const accessible = await canAccessCase(req.user.id, req.params.caseId);
    if (!accessible) return res.status(404).json({ error: 'Mangel nicht gefunden.' });
    const note = cleanText(req.body.note, 2000);
    if (!note) return res.status(400).json({ error: 'Notiz darf nicht leer sein.' });
    const result = await pool.query(
      'INSERT INTO case_events (id, case_id, user_id, event_type, note) VALUES ($1,$2,$3,$4,$5) RETURNING *',
      [id(), req.params.caseId, req.user.id, 'note', note]
    );
    await pool.query('UPDATE defect_cases SET updated_at=now() WHERE id=$1', [req.params.caseId]);
    res.status(201).json({ event: result.rows[0] });
  } catch (error) {
    next(error);
  }
});

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, uploadDir),
  filename: (_req, file, cb) => {
    const ext = path.extname(file.originalname).toLowerCase().slice(0, 10);
    cb(null, `${id()}${ext}`);
  }
});

const upload = multer({
  storage,
  limits: { fileSize: 10 * 1024 * 1024, files: 5 },
  fileFilter: (_req, file, cb) => cb(null, /^image\/(jpeg|png|webp|heic|heif)$/.test(file.mimetype))
});

app.post('/api/cases/:caseId/attachments', auth, upload.array('images', 5), async (req, res, next) => {
  try {
    const accessible = await canAccessCase(req.user.id, req.params.caseId);
    if (!accessible) return res.status(404).json({ error: 'Mangel nicht gefunden.' });
    const created = [];
    for (const file of req.files || []) {
      const attachmentId = id();
      const result = await pool.query(
        `INSERT INTO attachments (id,case_id,user_id,original_name,stored_name,mime_type,size_bytes)
         VALUES ($1,$2,$3,$4,$5,$6,$7)
         RETURNING id, original_name, mime_type, size_bytes, created_at`,
        [attachmentId, req.params.caseId, req.user.id, cleanText(file.originalname, 250), file.filename, file.mimetype, file.size]
      );
      created.push(result.rows[0]);
    }
    await pool.query('UPDATE defect_cases SET updated_at=now() WHERE id=$1', [req.params.caseId]);
    res.status(201).json({ attachments: created });
  } catch (error) {
    next(error);
  }
});

app.get('/api/attachments/:attachmentId', auth, async (req, res, next) => {
  try {
    const result = await pool.query(`SELECT a.* FROM attachments a JOIN defect_cases c ON c.id=a.case_id WHERE a.id=$1 AND (c.user_id=$2 OR (c.organization_id IS NOT NULL AND EXISTS (SELECT 1 FROM organization_memberships om WHERE om.organization_id=c.organization_id AND om.user_id=$2)))`, [req.params.attachmentId, req.user.id]);
    if (!result.rowCount) return res.status(404).end();
    const item = result.rows[0];
    res.type(item.mime_type).sendFile(path.join(uploadDir, item.stored_name));
  } catch (error) {
    next(error);
  }
});

app.get('/api/cases/:caseId/pdf', auth, async (req, res, next) => {
  try {
    const [caseResult, attachmentResult] = await Promise.all([
      pool.query(`SELECT c.* FROM defect_cases c WHERE c.id=$1 AND (c.user_id=$2 OR (c.organization_id IS NOT NULL AND EXISTS (SELECT 1 FROM organization_memberships om WHERE om.organization_id=c.organization_id AND om.user_id=$2)))`, [req.params.caseId, req.user.id]),
      pool.query('SELECT * FROM attachments WHERE case_id=$1 ORDER BY created_at', [req.params.caseId])
    ]);
    if (!caseResult.rowCount) return res.status(404).json({ error: 'Mangel nicht gefunden.' });

    const item = caseResult.rows[0];
    const attachments = attachmentResult.rows;
    const doc = new PDFDocument({
      size: 'A4',
      margins: { top: 42, right: 46, bottom: 45, left: 46 },
      info: { Title: `MängelFix – ${item.title}`, Author: req.user.name || 'MängelFix' }
    });

    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', `attachment; filename="maengelfix-${item.id}.pdf"`);
    doc.pipe(res);

    const C = {
      ink: '#18212B',
      muted: '#6F7A86',
      line: '#DFE4E8',
      panel: '#F4F6F8',
      blue: '#2457D6',
      blueSoft: '#EAF0FF',
      amber: '#E4A11B',
      amberSoft: '#FFF7E8',
      white: '#FFFFFF'
    };
    const pageW = doc.page.width;
    const pageH = doc.page.height;
    const left = 46;
    const right = pageW - 46;
    const width = right - left;
    const maxY = pageH - 70;
    const date = value => value ? new Date(value).toLocaleDateString('de-DE') : '—';
    const statusText = {
      draft: 'Entwurf',
      sent: 'Versendet',
      reply: 'Rückmeldung',
      in_progress: 'In Bearbeitung',
      resolved: 'Erledigt'
    }[item.status] || item.status;
    const shortId = String(item.id).split('-')[0].toUpperCase();

    const footer = () => {
      const lineY = pageH - 67;
      const textY = pageH - 57;
      doc.save();
      doc.moveTo(left, lineY).lineTo(right, lineY).strokeColor(C.line).lineWidth(0.7).stroke();
      doc.font('Helvetica').fontSize(7.5).fillColor(C.muted)
        .text('MängelFix · Dokumentation und Organisation · keine Rechtsberatung', left, textY, { width: width * 0.7, lineBreak: false });
      doc.text(`Vorgang ${shortId}`, left + width * 0.7, textY, { width: width * 0.3, align: 'right', lineBreak: false });
      doc.restore();
    };

    const pageHeader = (subtitle = 'MÄNGELANZEIGE / DOKUMENTATION') => {
      doc.rect(0, 0, pageW, 78).fill(C.ink);
      doc.roundedRect(left, 23, 32, 32, 6).fill(C.white);
      // MängelFix-Dokumentlogo: Blatt + Haken statt Platzhalter 'MF'
      doc.save();
      doc.strokeColor(C.ink).lineWidth(1.4);
      doc.roundedRect(left + 8, 29, 15, 19, 2).stroke();
      doc.moveTo(left + 18, 29).lineTo(left + 23, 34).lineTo(left + 18, 34).stroke();
      doc.strokeColor(C.blue).lineWidth(2.0);
      doc.moveTo(left + 11, 40).lineTo(left + 15, 44).lineTo(left + 22, 36).stroke();
      doc.restore();
      doc.font('Helvetica-Bold').fontSize(17).fillColor(C.white).text('MängelFix', left + 44, 24, { lineBreak: false });
      doc.font('Helvetica').fontSize(7.5).fillColor('#B8C0C8').text(subtitle, left + 44, 47, { characterSpacing: 1.05, lineBreak: false });
      doc.font('Helvetica').fontSize(7.5).fillColor('#B8C0C8').text('VORGANG', right - 160, 24, { width: 160, align: 'right', lineBreak: false });
      doc.font('Helvetica-Bold').fontSize(10).fillColor(C.white).text(shortId, right - 160, 38, { width: 160, align: 'right', lineBreak: false });
      doc.font('Helvetica').fontSize(7.5).fillColor('#B8C0C8').text(new Date().toLocaleDateString('de-DE'), right - 160, 53, { width: 160, align: 'right', lineBreak: false });
      doc.y = 96;
    };

    const sectionTitle = text => {
      doc.font('Helvetica-Bold').fontSize(8).fillColor(C.blue).text(text.toUpperCase(), left, doc.y, { characterSpacing: 0.9 });
      doc.y += 17;
    };

    const card = (x, y, w, h, label, value) => {
      doc.roundedRect(x, y, w, h, 5).fill(C.panel);
      doc.font('Helvetica').fontSize(7).fillColor(C.muted).text(label, x + 10, y + 8, { width: w - 20, lineBreak: false });
      doc.font('Helvetica-Bold').fontSize(9.5).fillColor(C.ink).text(value || '—', x + 10, y + 22, { width: w - 20, height: h - 26, ellipsis: true });
    };

    pageHeader();

    const senderLines = [
      req.user.name,
      req.user.street,
      [req.user.postal_code, req.user.city].filter(Boolean).join(' '),
      req.user.country || 'Deutschland',
      req.user.email,
      req.user.phone
    ].filter(Boolean);
    const recipientLines = [item.recipient_name, item.recipient_address, item.recipient_email].filter(Boolean);

    const addressY = doc.y;
    const half = (width - 14) / 2;
    doc.font('Helvetica-Bold').fontSize(8).fillColor(C.muted).text('ABSENDER', left, addressY, { lineBreak: false });
    doc.font('Helvetica').fontSize(9.2).fillColor(C.ink).text(senderLines.length ? senderLines.join('\n') : 'Absenderprofil noch nicht vollständig', left, addressY + 15, { width: half, lineGap: 1.2 });
    doc.font('Helvetica-Bold').fontSize(8).fillColor(C.muted).text('EMPFÄNGER', left + half + 14, addressY, { lineBreak: false });
    doc.font('Helvetica').fontSize(9.2).fillColor(C.ink).text(recipientLines.length ? recipientLines.join('\n') : 'Noch kein Empfänger hinterlegt', left + half + 14, addressY + 15, { width: half, lineGap: 1.2 });
    doc.y = addressY + 86;

    doc.moveTo(left, doc.y).lineTo(right, doc.y).strokeColor(C.line).lineWidth(0.8).stroke();
    doc.y += 18;
    doc.font('Helvetica').fontSize(8).fillColor(C.blue).text(item.category || 'Mangel', left, doc.y, { characterSpacing: .6 });
    doc.y += 15;
    doc.font('Helvetica-Bold').fontSize(20).fillColor(C.ink).text(item.title, left, doc.y, { width });
    doc.y += 10;
    const titleBottom = doc.y;
    doc.roundedRect(left, titleBottom, 78, 20, 4).fill(C.blueSoft);
    doc.font('Helvetica-Bold').fontSize(7).fillColor(C.blue).text(statusText.toUpperCase(), left + 7, titleBottom + 7, { width: 64, align: 'center', lineBreak: false });
    doc.y = titleBottom + 34;

    const gap = 8;
    const boxW = (width - gap) / 2;
    let y = doc.y;
    card(left, y, boxW, 42, 'Objekt', item.property_label);
    card(left + boxW + gap, y, boxW, 42, 'Raum / Ort', item.location_label);
    y += 50;
    card(left, y, boxW, 42, 'Festgestellt am', date(item.discovered_on));
    card(left + boxW + gap, y, boxW, 42, 'Rückmeldung bis', date(item.deadline_on));
    doc.y = y + 58;

    const descHeight = doc.heightOfString(item.description || '', { width: width - 24, lineGap: 2.6 });
    const requestHeight = item.deadline_on ? 95 : 78;
    const required = 22 + Math.max(62, descHeight + 22) + 20 + requestHeight;

    if (doc.y + required > maxY) {
      footer();
      doc.addPage();
      pageHeader('MÄNGELANZEIGE · FORTSETZUNG');
    }

    sectionTitle('Beschreibung des Mangels');
    const descY = doc.y;
    const boxHeight = Math.max(62, doc.heightOfString(item.description || '', { width: width - 24, lineGap: 2.6 }) + 22);
    doc.roundedRect(left, descY, width, boxHeight, 6).fill(C.panel);
    doc.font('Helvetica').fontSize(10.2).fillColor(C.ink).text(item.description || '—', left + 12, descY + 11, { width: width - 24, lineGap: 2.6 });
    doc.y = descY + boxHeight + 18;

    sectionTitle('Mitteilung');
    doc.font('Helvetica').fontSize(10).fillColor(C.ink)
      .text('Hiermit zeige ich den oben beschriebenen Mangel an und bitte um Prüfung sowie eine Rückmeldung zum weiteren Vorgehen.', left, doc.y, { width, lineGap: 2.5 });
    if (item.deadline_on) {
      doc.y += 7;
      doc.font('Helvetica-Bold').fontSize(9.5).fillColor(C.ink)
        .text(`Gewünschtes Rückmeldedatum: ${date(item.deadline_on)}`, left, doc.y, { width });
    }
    doc.y += 16;
    doc.font('Helvetica').fontSize(9).fillColor(C.muted).text('Mit freundlichen Grüßen', left, doc.y);
    doc.y += 17;
    doc.font('Helvetica-Bold').fontSize(10).fillColor(C.ink).text(req.user.name || '—', left, doc.y);

    footer();

    const embeddable = attachments.filter(a => /^image\/(jpeg|png)$/.test(a.mime_type));
    if (embeddable.length) {
      let imageIndex = 0;
      while (imageIndex < embeddable.length) {
        doc.addPage();
        pageHeader(`FOTODOKUMENTATION · ${embeddable.length} BELEG${embeddable.length === 1 ? '' : 'E'}`);
        doc.font('Helvetica-Bold').fontSize(15).fillColor(C.ink).text(item.title, left, doc.y, { width });
        doc.y += 20;

        const imageGap = 10;
        const imageW = (width - imageGap) / 2;
        const imageH = 172;
        const cellH = 202;
        for (let row = 0; row < 3 && imageIndex < embeddable.length; row += 1) {
          const rowY = doc.y;
          for (let col = 0; col < 2 && imageIndex < embeddable.length; col += 1) {
            const attachment = embeddable[imageIndex++];
            const x = left + col * (imageW + imageGap);
            doc.roundedRect(x, rowY, imageW, cellH - 8, 6).strokeColor(C.line).lineWidth(.8).stroke();
            try {
              doc.image(path.join(uploadDir, attachment.stored_name), x + 7, rowY + 7, {
                fit: [imageW - 14, imageH - 14],
                align: 'center',
                valign: 'center'
              });
            } catch {
              doc.font('Helvetica').fontSize(8).fillColor(C.muted).text('Bild konnte nicht eingebettet werden.', x + 12, rowY + 72, { width: imageW - 24, align: 'center' });
            }
            doc.font('Helvetica').fontSize(7.5).fillColor(C.muted)
              .text(attachment.original_name || `Fotobeleg ${imageIndex}`, x + 8, rowY + imageH + 4, { width: imageW - 16, ellipsis: true });
          }
          doc.y = rowY + cellH;
        }
        footer();
      }
    }

    doc.end();
  } catch (error) {
    next(error);
  }
});

app.use(express.static(publicDir, { index: false, maxAge: production ? '1h' : 0 }));
app.use((req, res, next) => {
  if (req.method !== 'GET' || req.path.startsWith('/api/')) return next();
  res.sendFile(path.join(publicDir, 'index.html'));
});

app.use((error, _req, res, _next) => {
  console.error(error);
  if (error instanceof multer.MulterError) return res.status(400).json({ error: error.message });
  res.status(500).json({ error: 'Etwas ist schiefgelaufen.' });
});

app.listen(port, '0.0.0.0', () => {
  console.log(`MängelFix läuft auf Port ${port}`);
});
