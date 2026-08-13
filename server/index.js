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
import nodemailer from 'nodemailer';

const { Pool } = pg;
const scrypt = promisify(crypto.scrypt);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(__dirname, '..');
const publicDir = path.join(appRoot, 'public');
const uploadDir = process.env.UPLOAD_DIR || '/data/uploads';
const port = Number(process.env.PORT || 3000);
const cookieName = process.env.SESSION_COOKIE_NAME || 'maengelfix_session';
const production = process.env.NODE_ENV === 'production';
const appOrigin = process.env.APP_ORIGIN || 'https://maengelfix.kamilunavo.com';
const smtpConfigured = Boolean(process.env.SMTP_HOST && process.env.SMTP_USER && process.env.SMTP_PASS);
const mailer = smtpConfigured ? nodemailer.createTransport({ host: process.env.SMTP_HOST, port: Number(process.env.SMTP_PORT || 587), secure: String(process.env.SMTP_SECURE || 'false') === 'true', auth: { user: process.env.SMTP_USER, pass: process.env.SMTP_PASS } }) : null;

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
    phone: row.phone || '',
    emailVerified: Boolean(row.email_verified_at)
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
      `SELECT u.id, u.name, u.email, u.street, u.postal_code, u.city, u.country, u.phone, u.email_verified_at
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

const allowedStatuses = new Set(['draft','sent','reply','received','reviewing','commissioned','scheduled','in_progress','resolved']);


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


async function createNotification({ userId, organizationId=null, caseId=null, type, title, body=null, link=null }) {
  if (!userId) return;
  await pool.query(`INSERT INTO notifications (id,user_id,organization_id,case_id,type,title,body,link) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)`,
    [id(),userId,organizationId,caseId,type,title,body,link]);
}

async function notifyOrganization(organizationId, payload, excludeUserId=null) {
  if (!organizationId) return;
  const members=await pool.query('SELECT user_id FROM organization_memberships WHERE organization_id=$1',[organizationId]);
  await Promise.all(members.rows.filter(x=>x.user_id!==excludeUserId).map(x=>createNotification({userId:x.user_id,organizationId,...payload})));
}

async function writeAudit({ organizationId, userId=null, caseId=null, action, entityType, entityId=null, summary, metadata={} }) {
  if (!organizationId) return;
  await pool.query(`INSERT INTO audit_logs (id,organization_id,user_id,case_id,action,entity_type,entity_id,summary,metadata) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb)`,
    [id(),organizationId,userId,caseId,action,entityType,entityId,summary,JSON.stringify(metadata||{})]);
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
  res.json({ ok: true, service: 'maengelfix', version: '0.12.0', mail: smtpConfigured ? 'smtp' : 'manual' });
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
       RETURNING id, name, email, street, postal_code, city, country, phone, email_verified_at`,
      [userId, name, email, credentials.salt, credentials.hash]
    );
    await createSession(userId, res);
    try { await issueVerification(userId, email, name); } catch (mailError) { console.error('Verification mail failed', mailError); }
    res.status(201).json({ user: publicUser(result.rows[0]), verificationMailSent: Boolean(mailer) });
  } catch (error) {
    next(error);
  }
});

app.post('/api/auth/login', async (req, res, next) => {
  try {
    const email = cleanText(req.body.email, 254)?.toLowerCase();
    const password = String(req.body.password || '');
    const result = await pool.query(
      `SELECT id, name, email, password_salt, password_hash, street, postal_code, city, country, phone, email_verified_at
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


app.post('/api/auth/resend-verification', auth, async (req,res,next)=>{
  try {
    if (req.user.email_verified_at) return res.json({ok:true,alreadyVerified:true});
    const sent=await issueVerification(req.user.id,req.user.email,req.user.name);
    res.json({ok:true,sent});
  } catch(error){next(error);}
});

app.get('/api/auth/verify-email/:token', async (req,res,next)=>{
  const client=await pool.connect();
  try {
    await client.query('BEGIN');
    const result=await client.query(`SELECT * FROM email_verification_tokens WHERE token_hash=$1 FOR UPDATE`,[tokenHash(req.params.token)]);
    if(!result.rowCount){await client.query('ROLLBACK');return res.status(404).json({error:'Bestätigungslink nicht gefunden.'});}
    const token=result.rows[0];
    if(token.used_at || new Date(token.expires_at)<=new Date()){await client.query('ROLLBACK');return res.status(410).json({error:'Dieser Bestätigungslink ist abgelaufen oder wurde bereits verwendet.'});}
    await client.query('UPDATE users SET email_verified_at=now() WHERE id=$1',[token.user_id]);
    await client.query('UPDATE email_verification_tokens SET used_at=now() WHERE id=$1',[token.id]);
    await client.query('COMMIT');
    res.json({ok:true});
  } catch(error){await client.query('ROLLBACK');next(error);} finally{client.release();}
});

app.post('/api/auth/forgot-password', async (req,res,next)=>{
  try {
    const email=cleanText(req.body.email,254)?.toLowerCase();
    const result=await pool.query('SELECT id,name,email FROM users WHERE email=$1',[email]);
    if(result.rowCount && mailer){
      const user=result.rows[0];
      await pool.query(`UPDATE password_reset_tokens SET expires_at=now() WHERE user_id=$1 AND used_at IS NULL AND expires_at>now()`,[user.id]);
      const token=crypto.randomBytes(32).toString('base64url');
      await pool.query(`INSERT INTO password_reset_tokens (id,user_id,token_hash,expires_at) VALUES ($1,$2,$3,now()+interval '60 minutes')`,[id(),user.id,tokenHash(token)]);
      await sendAppMail({to:user.email,subject:'MängelFix Passwort zurücksetzen',heading:'Passwort zurücksetzen',text:'Du hast ein neues Passwort angefordert. Der Link ist 60 Minuten gültig. Wenn du das nicht warst, kannst du diese E-Mail ignorieren.',buttonLabel:'Neues Passwort festlegen',buttonUrl:`${appOrigin}/passwort-zuruecksetzen/${token}`});
    }
    res.json({ok:true,message:'Wenn ein Konto mit dieser E-Mail existiert, wurde eine Nachricht versendet.'});
  } catch(error){next(error);}
});

app.post('/api/auth/reset-password/:token', async (req,res,next)=>{
  const client=await pool.connect();
  try {
    const password=String(req.body.password||'');
    if(password.length<8) return res.status(400).json({error:'Das neue Passwort muss mindestens 8 Zeichen haben.'});
    await client.query('BEGIN');
    const result=await client.query(`SELECT * FROM password_reset_tokens WHERE token_hash=$1 FOR UPDATE`,[tokenHash(req.params.token)]);
    if(!result.rowCount){await client.query('ROLLBACK');return res.status(404).json({error:'Link nicht gefunden.'});}
    const token=result.rows[0];
    if(token.used_at || new Date(token.expires_at)<=new Date()){await client.query('ROLLBACK');return res.status(410).json({error:'Dieser Link ist abgelaufen oder wurde bereits verwendet.'});}
    const credentials=await makePassword(password);
    await client.query('UPDATE users SET password_salt=$2,password_hash=$3 WHERE id=$1',[token.user_id,credentials.salt,credentials.hash]);
    await client.query('UPDATE password_reset_tokens SET used_at=now() WHERE id=$1',[token.id]);
    await client.query('DELETE FROM sessions WHERE user_id=$1',[token.user_id]);
    await client.query('COMMIT');
    res.json({ok:true});
  } catch(error){await client.query('ROLLBACK');next(error);} finally{client.release();}
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
       RETURNING id, name, email, street, postal_code, city, country, phone, email_verified_at`,
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


app.post('/api/account/change-password', auth, async (req,res,next)=>{
  try {
    const current=String(req.body.currentPassword||''); const nextPassword=String(req.body.newPassword||'');
    if(nextPassword.length<8) return res.status(400).json({error:'Das neue Passwort muss mindestens 8 Zeichen haben.'});
    const r=await pool.query('SELECT password_salt,password_hash FROM users WHERE id=$1',[req.user.id]);
    if(!r.rowCount || !(await verifyPassword(current,r.rows[0].password_salt,r.rows[0].password_hash))) return res.status(401).json({error:'Das aktuelle Passwort ist nicht korrekt.'});
    const c=await makePassword(nextPassword); await pool.query('UPDATE users SET password_salt=$2,password_hash=$3 WHERE id=$1',[req.user.id,c.salt,c.hash]);
    const token=req.cookies[cookieName]; await pool.query('DELETE FROM sessions WHERE user_id=$1 AND token_hash<>$2',[req.user.id, token?tokenHash(token):'']);
    res.json({ok:true});
  } catch(error){next(error)}
});

app.patch('/api/account/email', auth, async (req,res,next)=>{
  try {
    const password=String(req.body.password||''); const email=cleanText(req.body.email,254)?.toLowerCase();
    if(!email||!email.includes('@')) return res.status(400).json({error:'Bitte gib eine gültige E-Mail-Adresse an.'});
    const r=await pool.query('SELECT password_salt,password_hash FROM users WHERE id=$1',[req.user.id]);
    if(!(await verifyPassword(password,r.rows[0].password_salt,r.rows[0].password_hash))) return res.status(401).json({error:'Das Passwort ist nicht korrekt.'});
    const exists=await pool.query('SELECT 1 FROM users WHERE email=$1 AND id<>$2',[email,req.user.id]); if(exists.rowCount) return res.status(409).json({error:'Diese E-Mail-Adresse wird bereits verwendet.'});
    await pool.query('UPDATE users SET email=$2,email_verified_at=NULL WHERE id=$1',[req.user.id,email]);
    try{await issueVerification(req.user.id,email,req.user.name)}catch(e){console.error('Verification after email change failed',e)}
    res.json({ok:true,email,verificationMailSent:Boolean(mailer)});
  } catch(error){next(error)}
});

app.get('/api/account/export', auth, async (req,res,next)=>{
  try {
    const [user,cases,links,memberships]=await Promise.all([
      pool.query('SELECT id,name,email,street,postal_code,city,country,phone,email_verified_at,created_at FROM users WHERE id=$1',[req.user.id]),
      pool.query(`SELECT c.*, COALESCE(json_agg(DISTINCT jsonb_build_object('id',a.id,'name',a.original_name,'mimeType',a.mime_type,'size',a.size_bytes,'createdAt',a.created_at)) FILTER (WHERE a.id IS NOT NULL),'[]') attachments FROM defect_cases c LEFT JOIN attachments a ON a.case_id=c.id WHERE c.user_id=$1 GROUP BY c.id ORDER BY c.created_at`,[req.user.id]),
      pool.query(`SELECT tl.id,tl.status,tl.created_at,tl.disconnected_at,o.name organization,p.name property,u.label unit FROM tenant_links tl JOIN organizations o ON o.id=tl.organization_id JOIN properties p ON p.id=tl.property_id JOIN units u ON u.id=tl.unit_id WHERE tl.user_id=$1`,[req.user.id]),
      pool.query(`SELECT om.organization_id,o.name,om.role,COALESCE(om.active,true) active,om.created_at FROM organization_memberships om JOIN organizations o ON o.id=om.organization_id WHERE om.user_id=$1`,[req.user.id])
    ]);
    const payload={exportedAt:new Date().toISOString(),account:user.rows[0],cases:cases.rows,tenantLinks:links.rows,organizations:memberships.rows};
    res.setHeader('Content-Type','application/json; charset=utf-8'); res.setHeader('Content-Disposition','attachment; filename="maengelfix-datenexport.json"'); res.send(JSON.stringify(payload,null,2));
  } catch(error){next(error)}
});

app.post('/api/tenant-links/:linkId/disconnect', auth, async (req,res,next)=>{
  try {
    const r=await pool.query(`UPDATE tenant_links SET status='disconnected',disconnected_at=now(),disconnected_by=$2 WHERE id=$1 AND user_id=$2 AND status='active' RETURNING id`,[req.params.linkId,req.user.id]);
    if(!r.rowCount) return res.status(404).json({error:'Aktive Verknüpfung nicht gefunden.'}); res.json({ok:true});
  } catch(error){next(error)}
});

app.patch('/api/team/members/:userId/status', auth, async (req,res,next)=>{
  try {
    const org=await organizationForUser(req.user.id); if(!org||!['owner','admin'].includes(org.role)) return res.status(403).json({error:'Keine Berechtigung.'});
    if(req.params.userId===req.user.id) return res.status(400).json({error:'Deinen eigenen Zugang kannst du hier nicht deaktivieren.'});
    const target=await pool.query('SELECT role FROM organization_memberships WHERE organization_id=$1 AND user_id=$2',[org.id,req.params.userId]); if(!target.rowCount) return res.status(404).json({error:'Mitarbeiter nicht gefunden.'});
    if(target.rows[0].role==='owner') return res.status(400).json({error:'Der Inhaber kann nicht deaktiviert werden.'});
    const active=Boolean(req.body.active); await pool.query(`UPDATE organization_memberships SET active=$3,deactivated_at=CASE WHEN $3 THEN NULL ELSE now() END,deactivated_by=CASE WHEN $3 THEN NULL ELSE $4 END WHERE organization_id=$1 AND user_id=$2`,[org.id,req.params.userId,active,req.user.id]);
    if(!active) await pool.query('DELETE FROM sessions WHERE user_id=$1',[req.params.userId]); res.json({ok:true,active});
  } catch(error){next(error)}
});

app.post('/api/team/transfer-ownership', auth, async (req,res,next)=>{
  const client=await pool.connect(); try {
    const org=await organizationForUser(req.user.id); if(!org||org.role!=='owner') return res.status(403).json({error:'Nur der aktuelle Inhaber kann die Inhaberschaft übertragen.'});
    const targetId=cleanText(req.body.userId,80); const t=await client.query(`SELECT role,COALESCE(active,true) active FROM organization_memberships WHERE organization_id=$1 AND user_id=$2`,[org.id,targetId]); if(!t.rowCount||!t.rows[0].active) return res.status(400).json({error:'Bitte wähle einen aktiven Mitarbeiter.'});
    await client.query('BEGIN'); await client.query(`UPDATE organization_memberships SET role='admin' WHERE organization_id=$1 AND user_id=$2`,[org.id,req.user.id]); await client.query(`UPDATE organization_memberships SET role='owner' WHERE organization_id=$1 AND user_id=$2`,[org.id,targetId]); await client.query('COMMIT'); res.json({ok:true});
  } catch(error){await client.query('ROLLBACK');next(error)} finally{client.release()}
});

app.post('/api/team/leave', auth, async (req,res,next)=>{
  try {
    const org=await organizationForUser(req.user.id); if(!org) return res.status(404).json({error:'Du gehörst zu keinem Verwaltungs-Arbeitsbereich.'}); if(org.role==='owner') return res.status(400).json({error:'Übertrage zuerst die Inhaberschaft, bevor du die Organisation verlässt.'});
    await pool.query('DELETE FROM organization_memberships WHERE organization_id=$1 AND user_id=$2',[org.id,req.user.id]); res.json({ok:true});
  } catch(error){next(error)}
});

app.delete('/api/account', auth, async (req,res,next)=>{
  const client=await pool.connect(); try {
    const password=String(req.body.password||''); const confirmation=String(req.body.confirmation||''); if(confirmation!=='LÖSCHEN') return res.status(400).json({error:'Bitte gib zur Bestätigung LÖSCHEN ein.'});
    const u=await client.query('SELECT password_salt,password_hash FROM users WHERE id=$1',[req.user.id]); if(!(await verifyPassword(password,u.rows[0].password_salt,u.rows[0].password_hash))) return res.status(401).json({error:'Das Passwort ist nicht korrekt.'});
    const owned=await client.query(`SELECT o.id,o.name FROM organizations o JOIN organization_memberships om ON om.organization_id=o.id WHERE om.user_id=$1 AND om.role='owner' AND COALESCE(om.active,true)=true`,[req.user.id]); if(owned.rowCount) return res.status(409).json({error:`Du bist noch Inhaber von „${owned.rows[0].name}“. Übertrage zuerst die Inhaberschaft.`});
    await client.query('BEGIN'); await client.query('DELETE FROM users WHERE id=$1',[req.user.id]); await client.query('COMMIT'); res.clearCookie(cookieName,{path:'/'}); res.json({ok:true});
  } catch(error){await client.query('ROLLBACK');next(error)} finally{client.release()}
});

app.get('/api/billing/plan', auth, async (req,res,next)=>{
  try {
    const org=await billingOrganizationForUser(req.user.id);
    if(org){const usage=await billingUsage(org.id);return res.json({scope:'organization',plan:{...org,...billingState(org)},usage,checkoutConfigured:Boolean(process.env.STRIPE_SECRET_KEY&&process.env.STRIPE_PRICE_MANAGEMENT)});}
    const r=await pool.query('SELECT plan_code,subscription_status,subscription_provider,subscription_current_period_end FROM users WHERE id=$1',[req.user.id]);
    res.json({scope:'private',plan:r.rows[0],checkoutConfigured:Boolean(process.env.STRIPE_SECRET_KEY&&process.env.STRIPE_PRICE_PRIVATE)});
  } catch(error){next(error)}
});

app.post('/api/billing/checkout', auth, async (req,res,next)=>{
  try {
    const org=await billingOrganizationForUser(req.user.id);
    if(org&&!['owner','admin'].includes(org.role)) return res.status(403).json({error:'Nur Inhaber und Admins können den Tarif ändern.'});
    const configured=Boolean(process.env.STRIPE_SECRET_KEY && (org?process.env.STRIPE_PRICE_MANAGEMENT:process.env.STRIPE_PRICE_PRIVATE));
    if(!configured) return res.status(503).json({error:'Online-Zahlung ist noch nicht aktiviert. Testphase und Tariflimits funktionieren bereits.'});
    return res.status(501).json({error:'Stripe Checkout wird erst aktiviert, nachdem die endgültigen Preise und Produkt-IDs festgelegt wurden.'});
  } catch(error){next(error)}
});

app.get('/api/team', auth, async (req, res, next) => {
  try {
    const organization = await organizationForUser(req.user.id);
    if (!organization) return res.json({ organization: null, members: [] });
    const members = await pool.query(
      `SELECT u.id, u.name, u.email, om.role, om.created_at, COALESCE(om.active,true) AS active, om.deactivated_at
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
        `INSERT INTO organizations (id,name,plan_code,created_by,subscription_status,trial_ends_at,max_members,max_properties,max_units) VALUES ($1,$2,'business_trial',$3,'trialing',now()+interval '14 days',5,25,250)`,
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
    res.status(201).json({ organization: { id: orgId, name, plan_code: 'business_trial', role: 'owner', subscription_status: 'trialing' } });
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
    const capacity=await enforceOrganizationLimit(organization,'member'); if(!capacity.ok) return res.status(402).json({error:capacity.error});
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



async function billingOrganizationForUser(userId) {
  const r=await pool.query(`SELECT o.*,om.role FROM organization_memberships om JOIN organizations o ON o.id=om.organization_id WHERE om.user_id=$1 AND COALESCE(om.active,true)=true LIMIT 1`,[userId]);
  return r.rows[0]||null;
}
function billingState(org){
  if(!org) return {active:false,reason:'none'};
  if(org.subscription_status==='trialing'){
    if(org.trial_ends_at && new Date(org.trial_ends_at)<=new Date()) return {active:false,reason:'trial_expired'};
    return {active:true,reason:'trialing'};
  }
  if(org.subscription_status==='active') return {active:true,reason:'active'};
  return {active:false,reason:org.subscription_status||'inactive'};
}
async function billingUsage(organizationId){
  const r=await pool.query(`SELECT
    (SELECT count(*)::int FROM organization_memberships WHERE organization_id=$1 AND COALESCE(active,true)=true) members,
    (SELECT count(*)::int FROM properties WHERE organization_id=$1) properties,
    (SELECT count(*)::int FROM units u JOIN properties p ON p.id=u.property_id WHERE p.organization_id=$1) units`,[organizationId]);
  return r.rows[0];
}
async function enforceOrganizationLimit(org,kind){
  const state=billingState(org); if(!state.active) return {ok:false,error:'Die Testphase bzw. das Verwaltungs-Abo ist nicht aktiv.'};
  const usage=await billingUsage(org.id); const uk={member:'members',property:'properties',unit:'units'}[kind]; const lk={member:'max_members',property:'max_properties',unit:'max_units'}[kind];
  if(uk && Number(usage[uk])>=Number(org[lk])) return {ok:false,error:`Tariflimit erreicht (${usage[uk]}/${org[lk]}).`};
  return {ok:true,usage};
}

async function scopeForUser(userId) {
  const organization = await organizationForUser(userId);
  return { organization, organizationId: organization?.id || null };
}





function escapeHtml(value) {
  return String(value || '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[ch]));
}

async function sendAppMail({ to, subject, heading, text, buttonLabel, buttonUrl }) {
  if (!mailer || !to) return false;
  const safeHeading=escapeHtml(heading || subject);
  const safeText=escapeHtml(text).replace(/\n/g,'<br>');
  const button=buttonUrl ? `<p style="margin:28px 0"><a href="${escapeHtml(buttonUrl)}" style="background:#2457d6;color:white;text-decoration:none;padding:12px 18px;border-radius:6px;display:inline-block">${escapeHtml(buttonLabel || 'MängelFix öffnen')}</a></p>` : '';
  await mailer.sendMail({
    from: process.env.SMTP_FROM || 'MängelFix <noreply@kamilunavo.com>', to, subject,
    text: `${heading || subject}\n\n${text}${buttonUrl ? `\n\n${buttonLabel || 'MängelFix öffnen'}: ${buttonUrl}` : ''}`,
    html: `<div style="font-family:Arial,sans-serif;max-width:620px;margin:auto;color:#18212b"><div style="font-weight:700;font-size:20px;margin-bottom:24px">MängelFix</div><h2>${safeHeading}</h2><p style="line-height:1.6">${safeText}</p>${button}<p style="color:#6f7a86;font-size:12px;margin-top:32px">Diese Nachricht wurde automatisch von MängelFix gesendet.</p></div>`
  });
  return true;
}

async function issueVerification(userId, email, name) {
  if (!mailer) return false;
  await pool.query(`UPDATE email_verification_tokens SET expires_at=now() WHERE user_id=$1 AND used_at IS NULL AND expires_at>now()`, [userId]);
  const token=crypto.randomBytes(32).toString('base64url');
  await pool.query(`INSERT INTO email_verification_tokens (id,user_id,token_hash,expires_at) VALUES ($1,$2,$3,now()+interval '24 hours')`, [id(),userId,tokenHash(token)]);
  return sendAppMail({to:email,subject:'E-Mail-Adresse für MängelFix bestätigen',heading:`Hallo ${name || ''}`,text:'Bitte bestätige deine E-Mail-Adresse. Der Link ist 24 Stunden gültig.',buttonLabel:'E-Mail bestätigen',buttonUrl:`${appOrigin}/email-bestaetigen/${token}`});
}

async function notifyOrganization(organizationId, subject, text, caseId) {
  if (!mailer || !organizationId) return;
  const result=await pool.query(`SELECT DISTINCT u.email FROM organization_memberships om JOIN users u ON u.id=om.user_id WHERE om.organization_id=$1`, [organizationId]);
  await Promise.allSettled(result.rows.map(row=>sendAppMail({to:row.email,subject,heading:subject,text,buttonLabel:'Vorgang öffnen',buttonUrl:`${appOrigin}/app?case=${caseId}`})));
}

async function tenantOwnerForCase(caseId) {
  const result=await pool.query(`SELECT u.id,u.name,u.email,c.title,c.status,c.organization_id,c.submitted_by_tenant,o.name AS organization_name FROM defect_cases c JOIN users u ON u.id=c.user_id LEFT JOIN organizations o ON o.id=c.organization_id WHERE c.id=$1`, [caseId]);
  return result.rows[0] || null;
}

async function sendTenantInvitationMail({ to, tenantName, organizationName, propertyName, unitLabel, inviteUrl }) {
  if (!mailer) return false;
  await mailer.sendMail({
    from: process.env.SMTP_FROM || 'MängelFix <noreply@kamilunavo.com>',
    to,
    subject: `${organizationName} lädt dich zu MängelFix ein`,
    text: `Hallo ${tenantName || ''},\n\n${organizationName} möchte dein MängelFix-Privatkonto mit ${propertyName} – ${unitLabel} verknüpfen. Die Verknüpfung ist freiwillig. Deine privaten Vorgänge bleiben privat. Nur Mängel, die du ausdrücklich an die Hausverwaltung übermittelst, werden dort sichtbar.\n\nEinladung öffnen: ${inviteUrl}\n\nDer Link ist 7 Tage gültig.`,
    html: `<div style="font-family:Arial,sans-serif;max-width:620px;margin:auto;color:#18212b"><h2 style="margin-bottom:6px">MängelFix</h2><p><b>${organizationName}</b> möchte dein MängelFix-Privatkonto mit <b>${propertyName} – ${unitLabel}</b> verknüpfen.</p><p>Die Verknüpfung ist freiwillig. Deine privaten Vorgänge bleiben privat. Nur Mängel, die du ausdrücklich an die Hausverwaltung übermittelst, werden dort sichtbar.</p><p style="margin:28px 0"><a href="${inviteUrl}" style="background:#2457d6;color:white;text-decoration:none;padding:12px 18px;border-radius:6px">Einladung öffnen</a></p><p style="color:#6f7a86;font-size:13px">Der Link ist 7 Tage gültig.</p></div>`
  });
  return true;
}

app.post('/api/contacts/:contactId/invitations', auth, async (req, res, next) => {
  try {
    const organization = await organizationForUser(req.user.id);
    if (!organization || !['owner','admin'].includes(organization.role)) return res.status(403).json({ error: 'Nur Inhaber und Admins können Mieter einladen.' });
    const unitId = cleanText(req.body.unitId, 80);
    const row = await pool.query(`SELECT c.id AS contact_id,c.name,c.email,u.id AS unit_id,u.label AS unit_label,p.id AS property_id,p.name AS property_name,p.allow_tenant_submissions,o.name AS organization_name
      FROM contacts c JOIN unit_contacts uc ON uc.contact_id=c.id JOIN units u ON u.id=uc.unit_id JOIN properties p ON p.id=u.property_id JOIN organizations o ON o.id=p.organization_id
      WHERE c.id=$1 AND u.id=$2 AND p.organization_id=$3`, [req.params.contactId, unitId, organization.id]);
    if (!row.rowCount) return res.status(404).json({ error: 'Mieter oder Einheit nicht gefunden.' });
    const tenant=row.rows[0];
    if (!tenant.email) return res.status(400).json({ error: 'Für diesen Mieter ist keine E-Mail-Adresse hinterlegt.' });
    const active = await pool.query(`SELECT tl.id FROM tenant_links tl JOIN users usr ON usr.id=tl.user_id WHERE tl.unit_id=$1 AND lower(usr.email)=lower($2) AND tl.status='active'`, [unitId, tenant.email]);
    if (active.rowCount) return res.status(409).json({ error: 'Dieser Mieter ist bereits digital mit der Einheit verknüpft.' });
    await pool.query(`UPDATE tenant_invitations SET expires_at=now() WHERE contact_id=$1 AND unit_id=$2 AND accepted_at IS NULL AND expires_at>now()`, [tenant.contact_id, unitId]);
    const token=crypto.randomBytes(32).toString('base64url');
    const invitationId=id();
    await pool.query(`INSERT INTO tenant_invitations (id,token_hash,organization_id,property_id,unit_id,contact_id,email,created_by,expires_at) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,now()+interval '7 days')`, [invitationId,tokenHash(token),organization.id,tenant.property_id,unitId,tenant.contact_id,tenant.email.toLowerCase(),req.user.id]);
    const inviteUrl=`${appOrigin}/einladung/${token}`;
    let delivery='manual';
    try { if (await sendTenantInvitationMail({to:tenant.email,tenantName:tenant.name,organizationName:tenant.organization_name,propertyName:tenant.property_name,unitLabel:tenant.unit_label,inviteUrl})) delivery='email'; } catch (mailError) { console.error('Invitation mail failed', mailError); }
    res.status(201).json({ invitation: { id: invitationId, email: tenant.email, inviteUrl, delivery, expiresInDays: 7 } });
  } catch(error){ next(error); }
});

app.get('/api/invitations/:token', async (req,res,next)=>{
  try {
    const result=await pool.query(`SELECT ti.email,ti.expires_at,ti.accepted_at,o.name AS organization_name,p.name AS property_name,p.street,p.postal_code,p.city,u.label AS unit_label,c.name AS contact_name
      FROM tenant_invitations ti JOIN organizations o ON o.id=ti.organization_id JOIN properties p ON p.id=ti.property_id JOIN units u ON u.id=ti.unit_id JOIN contacts c ON c.id=ti.contact_id
      WHERE ti.token_hash=$1`, [tokenHash(req.params.token)]);
    if (!result.rowCount) return res.status(404).json({error:'Einladung nicht gefunden.'});
    const invitation=result.rows[0];
    if (invitation.accepted_at) return res.status(410).json({error:'Diese Einladung wurde bereits angenommen.'});
    if (new Date(invitation.expires_at)<=new Date()) return res.status(410).json({error:'Diese Einladung ist abgelaufen. Bitte fordere eine neue Einladung an.'});
    res.json({ invitation });
  } catch(error){ next(error); }
});

app.post('/api/invitations/:token/accept', auth, async (req,res,next)=>{
  const client=await pool.connect();
  try {
    await client.query('BEGIN');
    const result=await client.query(`SELECT ti.* FROM tenant_invitations ti WHERE ti.token_hash=$1 FOR UPDATE`, [tokenHash(req.params.token)]);
    if (!result.rowCount) { await client.query('ROLLBACK'); return res.status(404).json({error:'Einladung nicht gefunden.'}); }
    const inv=result.rows[0];
    if (inv.accepted_at || new Date(inv.expires_at)<=new Date()) { await client.query('ROLLBACK'); return res.status(410).json({error:'Diese Einladung ist nicht mehr gültig.'}); }
    if (String(req.user.email).toLowerCase() !== String(inv.email).toLowerCase()) { await client.query('ROLLBACK'); return res.status(403).json({error:`Diese Einladung wurde an ${inv.email} gesendet. Bitte melde dich mit genau dieser E-Mail-Adresse an.`}); }
    const linkId=id();
    const linked=await client.query(`INSERT INTO tenant_links (id,organization_id,property_id,unit_id,contact_id,user_id,status) VALUES ($1,$2,$3,$4,$5,$6,'active') ON CONFLICT (unit_id,user_id) DO UPDATE SET organization_id=EXCLUDED.organization_id,property_id=EXCLUDED.property_id,contact_id=EXCLUDED.contact_id,status='active' RETURNING *`, [linkId,inv.organization_id,inv.property_id,inv.unit_id,inv.contact_id,req.user.id]);
    await client.query(`UPDATE tenant_invitations SET accepted_at=now() WHERE id=$1`, [inv.id]);
    await client.query('COMMIT');
    const orgInfo=await pool.query('SELECT name FROM organizations WHERE id=$1',[inv.organization_id]);
    try { await notifyOrganization(inv.organization_id,'Mieter-Verknüpfung bestätigt',`${req.user.name} hat die digitale Verbindung zur Einheit bestätigt.`, inv.unit_id); } catch(mailError){ console.error('Acceptance notification failed',mailError); }
    res.json({ link: linked.rows[0] });
  } catch(error){ await client.query('ROLLBACK'); next(error); } finally { client.release(); }
});

app.get('/api/tenant-links', auth, async (req,res,next)=>{
  try {
    const result=await pool.query(`SELECT tl.id,tl.status,o.name AS organization_name,p.id AS property_id,p.name AS property_name,p.street,p.postal_code,p.city,p.allow_tenant_submissions,u.id AS unit_id,u.label AS unit_label,c.name AS contact_name
      FROM tenant_links tl JOIN organizations o ON o.id=tl.organization_id JOIN properties p ON p.id=tl.property_id JOIN units u ON u.id=tl.unit_id JOIN contacts c ON c.id=tl.contact_id
      WHERE tl.user_id=$1 AND tl.status='active' ORDER BY o.name,p.name,u.label`, [req.user.id]);
    res.json({ links: result.rows });
  } catch(error){ next(error); }
});

app.patch('/api/properties/:propertyId/tenant-submissions', auth, async (req,res,next)=>{
  try {
    const organization=await organizationForUser(req.user.id);
    if (!organization || !['owner','admin'].includes(organization.role)) return res.status(403).json({error:'Nur Inhaber und Admins können diese Einstellung ändern.'});
    const result=await pool.query(`UPDATE properties SET allow_tenant_submissions=$3,updated_at=now() WHERE id=$1 AND organization_id=$2 RETURNING *`, [req.params.propertyId,organization.id,Boolean(req.body.enabled)]);
    if (!result.rowCount) return res.status(404).json({error:'Objekt nicht gefunden.'});
    res.json({property:result.rows[0]});
  } catch(error){next(error);}
});



const workOrderStatuses = new Set(['draft','sent','accepted','scheduled','completed','declined']);

function contractorUrl(token) {
  return `${appOrigin}/auftrag/${token}`;
}

async function providerForOrganization(providerId, organizationId) {
  const result = await pool.query('SELECT * FROM service_providers WHERE id=$1 AND organization_id=$2 AND active=true', [providerId, organizationId]);
  return result.rows[0] || null;
}

async function sendWorkOrderMail({ provider, organization, item, portalUrl }) {
  if (!mailer || !provider.email) return false;
  const safeTitle = String(item.title || 'Arbeitsauftrag');
  await mailer.sendMail({
    from: process.env.SMTP_FROM || 'MängelFix <noreply@kamilunavo.com>',
    to: provider.email,
    subject: `Arbeitsauftrag von ${organization.name}: ${safeTitle}`,
    text: `${organization.name} hat Ihnen einen Arbeitsauftrag über MängelFix gesendet.\n\n${safeTitle}\n${item.description}\n\nAuftrag öffnen: ${portalUrl}\n\nDer Link ist 30 Tage gültig.`,
    html: `<div style="font-family:Arial,sans-serif;max-width:640px;margin:auto;color:#18212b"><h2 style="margin-bottom:4px">MängelFix</h2><p style="color:#66717d;margin-top:0">Digitaler Arbeitsauftrag</p><p><b>${organization.name}</b> hat Ihnen einen Arbeitsauftrag gesendet.</p><div style="background:#f4f6f8;padding:18px;border-radius:8px;margin:20px 0"><h3 style="margin-top:0">${safeTitle}</h3><p style="white-space:pre-wrap">${String(item.description || '')}</p></div><p><a href="${portalUrl}" style="background:#2457d6;color:#fff;text-decoration:none;padding:12px 18px;border-radius:6px;display:inline-block">Arbeitsauftrag öffnen</a></p><p style="font-size:12px;color:#7a8490">Der persönliche Link ist 30 Tage gültig und darf nur an die zuständige Person weitergegeben werden.</p></div>`
  });
  return true;
}

app.get('/api/providers', auth, async (req,res,next)=>{
  try {
    const organization=await organizationForUser(req.user.id);
    if(!organization) return res.status(403).json({error:'Dienstleister sind im Hausverwaltungs-Arbeitsbereich verfügbar.'});
    const result=await pool.query(`SELECT sp.*,
      (SELECT count(*)::int FROM work_orders wo WHERE wo.provider_id=sp.id) AS order_count,
      (SELECT count(*)::int FROM work_orders wo WHERE wo.provider_id=sp.id AND wo.status NOT IN ('completed','declined')) AS open_order_count
      FROM service_providers sp WHERE sp.organization_id=$1 AND sp.active=true ORDER BY sp.company_name`,[organization.id]);
    res.json({providers:result.rows});
  } catch(error){next(error);}
});

app.post('/api/providers', auth, async (req,res,next)=>{
  try {
    const organization=await organizationForUser(req.user.id);
    if(!organization || !['owner','admin'].includes(organization.role)) return res.status(403).json({error:'Nur Inhaber und Admins können Dienstleister anlegen.'});
    const companyName=cleanText(req.body.companyName,180); const trade=cleanText(req.body.trade,100)||'Sonstiges';
    if(!companyName) return res.status(400).json({error:'Bitte gib den Firmennamen an.'});
    const result=await pool.query(`INSERT INTO service_providers (id,organization_id,company_name,trade,contact_name,email,phone,street,postal_code,city,notes)
      VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) RETURNING *`,[id(),organization.id,companyName,trade,cleanText(req.body.contactName,160),cleanText(req.body.email,254)?.toLowerCase(),cleanText(req.body.phone,60),cleanText(req.body.street,180),cleanText(req.body.postalCode,20),cleanText(req.body.city,120),cleanText(req.body.notes,2000)]);
    res.status(201).json({provider:result.rows[0]});
  } catch(error){next(error);}
});

app.patch('/api/providers/:providerId', auth, async (req,res,next)=>{
  try {
    const organization=await organizationForUser(req.user.id);
    if(!organization || !['owner','admin'].includes(organization.role)) return res.status(403).json({error:'Nur Inhaber und Admins können Dienstleister bearbeiten.'});
    const current=await pool.query('SELECT * FROM service_providers WHERE id=$1 AND organization_id=$2',[req.params.providerId,organization.id]);
    if(!current.rowCount) return res.status(404).json({error:'Dienstleister nicht gefunden.'});
    const old=current.rows[0];
    const result=await pool.query(`UPDATE service_providers SET company_name=$3,trade=$4,contact_name=$5,email=$6,phone=$7,street=$8,postal_code=$9,city=$10,notes=$11,active=$12,updated_at=now() WHERE id=$1 AND organization_id=$2 RETURNING *`,[req.params.providerId,organization.id,cleanText(req.body.companyName??old.company_name,180),cleanText(req.body.trade??old.trade,100)||'Sonstiges',cleanText(req.body.contactName??old.contact_name,160),cleanText(req.body.email??old.email,254)?.toLowerCase(),cleanText(req.body.phone??old.phone,60),cleanText(req.body.street??old.street,180),cleanText(req.body.postalCode??old.postal_code,20),cleanText(req.body.city??old.city,120),cleanText(req.body.notes??old.notes,2000),req.body.active===undefined?old.active:Boolean(req.body.active)]);
    res.json({provider:result.rows[0]});
  } catch(error){next(error);}
});

app.get('/api/work-orders', auth, async (req,res,next)=>{
  try {
    const organization=await organizationForUser(req.user.id);
    if(!organization) return res.status(403).json({error:'Arbeitsaufträge sind im Hausverwaltungs-Arbeitsbereich verfügbar.'});
    const result=await pool.query(`SELECT wo.*,sp.company_name,sp.trade,sp.email AS provider_email,c.title AS case_title,c.property_label,c.location_label,p.name AS property_name,u.label AS unit_label
      FROM work_orders wo JOIN service_providers sp ON sp.id=wo.provider_id JOIN defect_cases c ON c.id=wo.case_id LEFT JOIN properties p ON p.id=c.property_id LEFT JOIN units u ON u.id=c.unit_id
      WHERE wo.organization_id=$1 ORDER BY wo.updated_at DESC`,[organization.id]);
    res.json({orders:result.rows});
  } catch(error){next(error);}
});

app.get('/api/cases/:caseId/work-orders', auth, async (req,res,next)=>{
  try {
    const accessible=await canAccessCase(req.user.id,req.params.caseId);
    if(!accessible) return res.status(404).json({error:'Mangel nicht gefunden.'});
    const organization=await organizationForUser(req.user.id);
    if(!organization || accessible.organization_id!==organization.id) return res.json({orders:[],providers:[]});
    const [orders,providers]=await Promise.all([
      pool.query(`SELECT wo.*,sp.company_name,sp.trade,sp.email AS provider_email FROM work_orders wo JOIN service_providers sp ON sp.id=wo.provider_id WHERE wo.case_id=$1 AND wo.organization_id=$2 ORDER BY wo.created_at DESC`,[req.params.caseId,organization.id]),
      pool.query(`SELECT id,company_name,trade,email,phone FROM service_providers WHERE organization_id=$1 AND active=true ORDER BY company_name`,[organization.id])
    ]);
    res.json({orders:orders.rows,providers:providers.rows});
  } catch(error){next(error);}
});

app.post('/api/cases/:caseId/work-orders', auth, async (req,res,next)=>{
  const client=await pool.connect();
  try {
    const organization=await organizationForUser(req.user.id);
    if(!organization) return res.status(403).json({error:'Nur Hausverwaltungen können Arbeitsaufträge erstellen.'});
    const accessible=await canAccessCase(req.user.id,req.params.caseId);
    if(!accessible || accessible.organization_id!==organization.id) return res.status(404).json({error:'Vorgang nicht gefunden.'});
    const provider=await providerForOrganization(cleanText(req.body.providerId,80),organization.id);
    if(!provider) return res.status(400).json({error:'Bitte wähle einen gültigen Dienstleister.'});
    const title=cleanText(req.body.title,180)||accessible.title;
    const description=cleanText(req.body.description,6000)||accessible.description;
    const token=crypto.randomBytes(32).toString('base64url'); const orderId=id();
    await client.query('BEGIN');
    const result=await client.query(`INSERT INTO work_orders (id,organization_id,case_id,provider_id,created_by,title,description,status,due_on,token_hash,token_expires_at)
      VALUES ($1,$2,$3,$4,$5,$6,$7,'draft',$8,$9,now()+interval '30 days') RETURNING *`,[orderId,organization.id,req.params.caseId,provider.id,req.user.id,title,description,req.body.dueOn||null,tokenHash(token)]);
    const portalUrl=contractorUrl(token); let delivery='manual';
    try { if(await sendWorkOrderMail({provider,organization,item:result.rows[0],portalUrl})) delivery='email'; } catch(mailError){ console.error('Work order mail failed',mailError); }
    const status=delivery==='email'?'sent':'draft';
    await client.query(`UPDATE work_orders SET status=$2,sent_at=CASE WHEN $2='sent' THEN now() ELSE NULL END,updated_at=now() WHERE id=$1`,[orderId,status]);
    await client.query(`INSERT INTO case_events (id,case_id,user_id,event_type,note,visibility) VALUES ($1,$2,$3,'note',$4,'internal')`,[id(),req.params.caseId,req.user.id,`Arbeitsauftrag an ${provider.company_name} erstellt${delivery==='email'?' und per E-Mail versendet':''}.`]);
    await writeAudit({organizationId:organization.id,userId:req.user.id,caseId:req.params.caseId,action:'work_order_created',entityType:'work_order',entityId:orderId,summary:`Arbeitsauftrag an ${provider.company_name} erstellt.`});
    await client.query('COMMIT');
    res.status(201).json({order:{...result.rows[0],status,company_name:provider.company_name},portalUrl,delivery});
  } catch(error){await client.query('ROLLBACK');next(error);} finally{client.release();}
});

app.post('/api/work-orders/:orderId/send', auth, async (req,res,next)=>{
  try {
    const organization=await organizationForUser(req.user.id);
    if(!organization) return res.status(403).json({error:'Nicht verfügbar.'});
    const result=await pool.query(`SELECT wo.*,sp.company_name,sp.email,sp.contact_name FROM work_orders wo JOIN service_providers sp ON sp.id=wo.provider_id WHERE wo.id=$1 AND wo.organization_id=$2`,[req.params.orderId,organization.id]);
    if(!result.rowCount) return res.status(404).json({error:'Arbeitsauftrag nicht gefunden.'});
    const order=result.rows[0]; if(!order.email) return res.status(400).json({error:'Beim Dienstleister ist keine E-Mail-Adresse hinterlegt.'});
    const token=crypto.randomBytes(32).toString('base64url'); const portalUrl=contractorUrl(token);
    await pool.query(`UPDATE work_orders SET token_hash=$2,token_expires_at=now()+interval '30 days',status='sent',sent_at=now(),updated_at=now() WHERE id=$1`,[order.id,tokenHash(token)]);
    await sendWorkOrderMail({provider:{email:order.email},organization,item:order,portalUrl});
    res.json({sent:true,portalUrl});
  } catch(error){next(error);}
});

app.get('/api/work-orders/:orderId/pdf', auth, async (req,res,next)=>{
  try {
    const organization=await organizationForUser(req.user.id);
    if(!organization) return res.status(403).end();
    const result=await pool.query(`SELECT wo.*,sp.company_name,sp.contact_name,sp.street AS provider_street,sp.postal_code AS provider_postal_code,sp.city AS provider_city,sp.email AS provider_email,sp.phone AS provider_phone,c.title AS case_title,c.category,c.description AS case_description,c.property_label,c.location_label,p.name AS property_name,p.street AS property_street,p.postal_code AS property_postal_code,p.city AS property_city,u.label AS unit_label,o.name AS organization_name
      FROM work_orders wo JOIN service_providers sp ON sp.id=wo.provider_id JOIN defect_cases c ON c.id=wo.case_id JOIN organizations o ON o.id=wo.organization_id LEFT JOIN properties p ON p.id=c.property_id LEFT JOIN units u ON u.id=c.unit_id WHERE wo.id=$1 AND wo.organization_id=$2`,[req.params.orderId,organization.id]);
    if(!result.rowCount) return res.status(404).json({error:'Arbeitsauftrag nicht gefunden.'});
    const x=result.rows[0]; const doc=new PDFDocument({size:'A4',margins:{top:44,right:48,bottom:48,left:48}}); res.type('application/pdf'); res.setHeader('Content-Disposition',`attachment; filename="arbeitsauftrag-${x.id.split('-')[0]}.pdf"`); doc.pipe(res);
    doc.rect(0,0,doc.page.width,84).fill('#18212B'); doc.fillColor('#FFFFFF').font('Helvetica-Bold').fontSize(20).text('MängelFix',48,24); doc.font('Helvetica').fontSize(9).fillColor('#B9C1C8').text('ARBEITSAUFTRAG',48,52,{characterSpacing:1.2});
    doc.fillColor('#18212B').font('Helvetica-Bold').fontSize(17).text(x.title,48,112,{width:499}); doc.font('Helvetica').fontSize(9).fillColor('#66717D').text(`Auftrag ${x.id.split('-')[0].toUpperCase()} · erstellt ${new Date(x.created_at).toLocaleDateString('de-DE')}`,48,140);
    const box=(label,value,y)=>{doc.roundedRect(48,y,499,52,5).fill('#F4F6F8');doc.fillColor('#6F7A86').font('Helvetica-Bold').fontSize(7.5).text(label,60,y+10);doc.fillColor('#18212B').font('Helvetica-Bold').fontSize(10).text(value||'—',60,y+25,{width:470});};
    box('AUFTRAGGEBER',x.organization_name,174); box('AUFTRAGNEHMER',[x.company_name,x.contact_name].filter(Boolean).join(' · '),234); box('OBJEKT / EINSATZORT',[x.property_name||x.property_label,x.unit_label,x.location_label,[x.property_street,[x.property_postal_code,x.property_city].filter(Boolean).join(' ')].filter(Boolean).join(', ')].filter(Boolean).join(' · '),294);
    doc.fillColor('#2457D6').font('Helvetica-Bold').fontSize(8).text('AUFGABENBESCHREIBUNG',48,374,{characterSpacing:1}); doc.fillColor('#18212B').font('Helvetica').fontSize(10).text(x.description,48,394,{width:499,lineGap:3});
    const yy=Math.max(doc.y+24,500); doc.moveTo(48,yy).lineTo(547,yy).strokeColor('#DFE4E8').stroke(); doc.fillColor('#6F7A86').fontSize(8).text(`Gewünschte Erledigung: ${x.due_on?new Date(x.due_on).toLocaleDateString('de-DE'):'nicht festgelegt'}`,48,yy+14); doc.text('Rückmeldung und Status können über den persönlichen MängelFix-Auftragslink erfolgen.',48,yy+30,{width:499});
    doc.fontSize(7.5).fillColor('#7A8490').text('MängelFix · Arbeitsauftrag · Kamilunavo',48,doc.page.height-60,{width:499,align:'center'}); doc.end();
  } catch(error){next(error);}
});

app.get('/api/contractor/work-orders/:token', async (req,res,next)=>{
  try {
    const result=await pool.query(`SELECT wo.id,wo.title,wo.description,wo.status,wo.due_on,wo.scheduled_for,wo.contractor_note,wo.created_at,wo.token_expires_at,sp.company_name,sp.trade,o.name AS organization_name,c.property_label,c.location_label,p.name AS property_name,p.street AS property_street,p.postal_code AS property_postal_code,p.city AS property_city,u.label AS unit_label
      FROM work_orders wo JOIN service_providers sp ON sp.id=wo.provider_id JOIN organizations o ON o.id=wo.organization_id JOIN defect_cases c ON c.id=wo.case_id LEFT JOIN properties p ON p.id=c.property_id LEFT JOIN units u ON u.id=c.unit_id WHERE wo.token_hash=$1`,[tokenHash(req.params.token)]);
    if(!result.rowCount) return res.status(404).json({error:'Arbeitsauftrag nicht gefunden.'}); const order=result.rows[0];
    if(new Date(order.token_expires_at)<=new Date()) return res.status(410).json({error:'Dieser Auftragslink ist abgelaufen. Bitte wenden Sie sich an die Hausverwaltung.'});
    res.json({order});
  } catch(error){next(error);}
});

app.post('/api/contractor/work-orders/:token/status', async (req,res,next)=>{
  try {
    const status=cleanText(req.body.status,30); if(!['accepted','scheduled','completed','declined'].includes(status)) return res.status(400).json({error:'Ungültiger Auftragsstatus.'});
    const current=await pool.query(`SELECT wo.*,sp.company_name,o.name AS organization_name,c.title AS case_title FROM work_orders wo JOIN service_providers sp ON sp.id=wo.provider_id JOIN organizations o ON o.id=wo.organization_id JOIN defect_cases c ON c.id=wo.case_id WHERE wo.token_hash=$1`,[tokenHash(req.params.token)]);
    if(!current.rowCount) return res.status(404).json({error:'Arbeitsauftrag nicht gefunden.'}); const old=current.rows[0]; if(new Date(old.token_expires_at)<=new Date()) return res.status(410).json({error:'Dieser Auftragslink ist abgelaufen.'});
    const scheduledFor=req.body.scheduledFor?new Date(req.body.scheduledFor):old.scheduled_for; if(req.body.scheduledFor && isNaN(scheduledFor.getTime())) return res.status(400).json({error:'Ungültiger Termin.'});
    const result=await pool.query(`UPDATE work_orders SET status=$2,scheduled_for=$3,contractor_note=$4,accepted_at=CASE WHEN $2='accepted' AND accepted_at IS NULL THEN now() ELSE accepted_at END,completed_at=CASE WHEN $2='completed' THEN now() ELSE completed_at END,updated_at=now() WHERE id=$1 RETURNING *`,[old.id,status,scheduledFor||null,cleanText(req.body.note,3000)]);
    await pool.query(`INSERT INTO case_events (id,case_id,user_id,event_type,note,visibility) VALUES ($1,$2,$3,'note',$4,'internal')`,[id(),old.case_id,old.created_by,`Dienstleister ${old.company_name}: Auftrag ${status==='accepted'?'angenommen':status==='scheduled'?'terminiert':status==='completed'?'als erledigt gemeldet':'abgelehnt'}${req.body.note?` – ${cleanText(req.body.note,500)}`:''}.`]);
    res.json({order:result.rows[0]});
  } catch(error){next(error);}
});




function calendarRange(req){
  const now=new Date(); const from=req.query.from?new Date(req.query.from):new Date(now.getFullYear(),now.getMonth(),1); const to=req.query.to?new Date(req.query.to):new Date(now.getFullYear(),now.getMonth()+1,1);
  return {from:isNaN(from.getTime())?new Date(now.getFullYear(),now.getMonth(),1):from,to:isNaN(to.getTime())?new Date(now.getFullYear(),now.getMonth()+1,1):to};
}

app.get('/api/calendar', auth, async (req,res,next)=>{
  try{
    const organization=await organizationForUser(req.user.id); const {from,to}=calendarRange(req); const mine=String(req.query.mine||'')==='1';
    let own,orders=[];
    if(organization){
      const params=[organization.id,from,to]; let extra=''; if(mine){params.push(req.user.id);extra=' AND ce.assigned_user_id=$4';}
      own=(await pool.query(`SELECT ce.*,c.title AS case_title,p.name AS property_name,u.label AS unit_label,usr.name AS assigned_name FROM calendar_events ce LEFT JOIN defect_cases c ON c.id=ce.case_id LEFT JOIN properties p ON p.id=ce.property_id LEFT JOIN units u ON u.id=ce.unit_id LEFT JOIN users usr ON usr.id=ce.assigned_user_id WHERE ce.organization_id=$1 AND ce.starts_at<$3 AND ce.ends_at>$2${extra} ORDER BY ce.starts_at`,params)).rows;
      orders=(await pool.query(`SELECT wo.id,wo.case_id,wo.scheduled_for,wo.title,wo.status,sp.company_name,c.property_label,c.location_label,p.name AS property_name,u.label AS unit_label FROM work_orders wo JOIN service_providers sp ON sp.id=wo.provider_id JOIN defect_cases c ON c.id=wo.case_id LEFT JOIN properties p ON p.id=c.property_id LEFT JOIN units u ON u.id=c.unit_id WHERE wo.organization_id=$1 AND wo.scheduled_for IS NOT NULL AND wo.scheduled_for>=$2 AND wo.scheduled_for<$3 ORDER BY wo.scheduled_for`,[organization.id,from,to])).rows.map(x=>({id:`workorder:${x.id}`,case_id:x.case_id,title:`${x.company_name}: ${x.title}`,event_type:'contractor',status:x.status,starts_at:x.scheduled_for,ends_at:new Date(new Date(x.scheduled_for).getTime()+90*60000).toISOString(),property_name:x.property_name||x.property_label,unit_label:x.unit_label||x.location_label,assigned_name:x.company_name,readonly:true,source:'work_order'}));
    }else{
      own=(await pool.query(`SELECT ce.*,c.title AS case_title FROM calendar_events ce LEFT JOIN defect_cases c ON c.id=ce.case_id WHERE ce.organization_id IS NULL AND ce.created_by=$1 AND ce.starts_at<$3 AND ce.ends_at>$2 ORDER BY ce.starts_at`,[req.user.id,from,to])).rows;
    }
    res.json({events:[...own,...orders].sort((a,b)=>new Date(a.starts_at)-new Date(b.starts_at)),organization:organization||null});
  }catch(error){next(error)}
});

app.get('/api/cases/:caseId/calendar', auth, async (req,res,next)=>{
  try{
    const accessible=await canAccessCase(req.user.id,req.params.caseId); if(!accessible)return res.status(404).json({error:'Vorgang nicht gefunden.'});
    const events=(await pool.query(`SELECT ce.*,u.name AS assigned_name FROM calendar_events ce LEFT JOIN users u ON u.id=ce.assigned_user_id WHERE ce.case_id=$1 ORDER BY ce.starts_at`,[req.params.caseId])).rows;
    const orders=(await pool.query(`SELECT wo.id,wo.title,wo.status,wo.scheduled_for,sp.company_name FROM work_orders wo JOIN service_providers sp ON sp.id=wo.provider_id WHERE wo.case_id=$1 AND wo.scheduled_for IS NOT NULL ORDER BY wo.scheduled_for`,[req.params.caseId])).rows.map(x=>({id:`workorder:${x.id}`,title:`${x.company_name}: ${x.title}`,event_type:'contractor',status:x.status,starts_at:x.scheduled_for,ends_at:new Date(new Date(x.scheduled_for).getTime()+90*60000).toISOString(),assigned_name:x.company_name,readonly:true}));
    let members=[]; if(accessible.organization_id){members=(await pool.query(`SELECT u.id,u.name FROM organization_memberships om JOIN users u ON u.id=om.user_id WHERE om.organization_id=$1 AND COALESCE(om.active,true)=true ORDER BY u.name`,[accessible.organization_id])).rows;}
    res.json({events:[...events,...orders].sort((a,b)=>new Date(a.starts_at)-new Date(b.starts_at)),members,organizationId:accessible.organization_id||null,tenantVisible:Boolean(accessible.submitted_by_tenant)});
  }catch(error){next(error)}
});

app.post('/api/cases/:caseId/calendar', auth, async (req,res,next)=>{
  try{
    const accessible=await canAccessCase(req.user.id,req.params.caseId); if(!accessible)return res.status(404).json({error:'Vorgang nicht gefunden.'});
    const title=cleanText(req.body.title,180); const starts=new Date(req.body.startsAt); const ends=new Date(req.body.endsAt); if(!title||isNaN(starts.getTime())||isNaN(ends.getTime())||ends<=starts)return res.status(400).json({error:'Titel sowie gültiger Start und Ende sind erforderlich.'});
    const eventType=['internal','tenant','inspection'].includes(req.body.eventType)?req.body.eventType:'internal'; let assigned=req.body.assignedUserId||req.user.id;
    if(accessible.organization_id){const m=await pool.query(`SELECT 1 FROM organization_memberships WHERE organization_id=$1 AND user_id=$2 AND COALESCE(active,true)=true`,[accessible.organization_id,assigned]);if(!m.rowCount)return res.status(400).json({error:'Ungültiger Mitarbeiter.'});}else assigned=req.user.id;
    const notifyTenant=Boolean(req.body.notifyTenant&&accessible.organization_id&&accessible.submitted_by_tenant);
    const eventId=id(); const result=await pool.query(`INSERT INTO calendar_events (id,organization_id,case_id,property_id,unit_id,created_by,assigned_user_id,event_type,title,notes,starts_at,ends_at,status,notify_tenant,reminder_at) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,'planned',$13,$14) RETURNING *`,[eventId,accessible.organization_id||null,req.params.caseId,accessible.property_id||null,accessible.unit_id||null,req.user.id,assigned,eventType,title,cleanText(req.body.notes,2000),starts,ends,notifyTenant,req.body.reminderAt||null]);
    if(accessible.organization_id){await writeAudit({organizationId:accessible.organization_id,userId:req.user.id,caseId:req.params.caseId,action:'calendar_event_created',entityType:'calendar_event',entityId:eventId,summary:`Termin „${title}“ angelegt.`});if(assigned!==req.user.id)await createNotification({userId:assigned,organizationId:accessible.organization_id,caseId:req.params.caseId,type:'appointment',title:'Neuer Termin für dich',body:`${title} · ${starts.toLocaleString('de-DE')}`,link:'/app?view=calendar'});}
    if(notifyTenant){const owner=await tenantOwnerForCase(req.params.caseId);if(owner){await createNotification({userId:owner.id,organizationId:accessible.organization_id,caseId:req.params.caseId,type:'appointment',title:'Neuer Termin zu deiner Mängelmeldung',body:`${title} · ${starts.toLocaleString('de-DE')}`,link:`/app?case=${req.params.caseId}`});if(mailer)try{await sendAppMail({to:owner.email,subject:`Termin zu: ${accessible.title}`,heading:'Neuer Termin',text:`${title}\n${starts.toLocaleString('de-DE')} – ${ends.toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'})}`,buttonLabel:'Vorgang öffnen',buttonUrl:`${appOrigin}/app?case=${req.params.caseId}`})}catch(e){console.error('Appointment tenant mail failed',e)}}}
    res.status(201).json({event:result.rows[0]});
  }catch(error){next(error)}
});

app.patch('/api/calendar/:eventId', auth, async (req,res,next)=>{
  try{
    const r=await pool.query('SELECT * FROM calendar_events WHERE id=$1',[req.params.eventId]);if(!r.rowCount)return res.status(404).json({error:'Termin nicht gefunden.'});const ev=r.rows[0];
    if(ev.organization_id){const org=await organizationForUser(req.user.id);if(!org||org.id!==ev.organization_id)return res.status(403).json({error:'Kein Zugriff.'});}else if(ev.created_by!==req.user.id)return res.status(403).json({error:'Kein Zugriff.'});
    const status=['planned','confirmed','completed','cancelled'].includes(req.body.status)?req.body.status:ev.status; const starts=req.body.startsAt?new Date(req.body.startsAt):new Date(ev.starts_at); const ends=req.body.endsAt?new Date(req.body.endsAt):new Date(ev.ends_at); if(isNaN(starts)||isNaN(ends)||ends<=starts)return res.status(400).json({error:'Ungültiger Zeitraum.'});
    let assigned=req.body.assignedUserId===undefined?ev.assigned_user_id:(req.body.assignedUserId||null);if(ev.organization_id&&assigned){const m=await pool.query(`SELECT 1 FROM organization_memberships WHERE organization_id=$1 AND user_id=$2 AND COALESCE(active,true)=true`,[ev.organization_id,assigned]);if(!m.rowCount)return res.status(400).json({error:'Ungültiger Mitarbeiter.'});}
    const result=await pool.query(`UPDATE calendar_events SET title=$2,notes=$3,starts_at=$4,ends_at=$5,status=$6,assigned_user_id=$7,reminder_at=$8,reminder_sent_at=CASE WHEN reminder_at IS DISTINCT FROM $8 THEN NULL ELSE reminder_sent_at END,completed_at=CASE WHEN $6='completed' THEN COALESCE(completed_at,now()) ELSE NULL END,updated_at=now() WHERE id=$1 RETURNING *`,[ev.id,cleanText(req.body.title??ev.title,180),cleanText(req.body.notes??ev.notes,2000),starts,ends,status,assigned,req.body.reminderAt===undefined?ev.reminder_at:(req.body.reminderAt||null)]);
    if(ev.organization_id)await writeAudit({organizationId:ev.organization_id,userId:req.user.id,caseId:ev.case_id,action:'calendar_event_updated',entityType:'calendar_event',entityId:ev.id,summary:`Termin „${ev.title}“ aktualisiert.`});res.json({event:result.rows[0]});
  }catch(error){next(error)}
});

app.delete('/api/calendar/:eventId', auth, async (req,res,next)=>{
  try{const r=await pool.query('SELECT * FROM calendar_events WHERE id=$1',[req.params.eventId]);if(!r.rowCount)return res.status(404).json({error:'Termin nicht gefunden.'});const ev=r.rows[0];if(ev.organization_id){const org=await organizationForUser(req.user.id);if(!org||org.id!==ev.organization_id)return res.status(403).json({error:'Kein Zugriff.'});}else if(ev.created_by!==req.user.id)return res.status(403).json({error:'Kein Zugriff.'});await pool.query('DELETE FROM calendar_events WHERE id=$1',[ev.id]);if(ev.organization_id)await writeAudit({organizationId:ev.organization_id,userId:req.user.id,caseId:ev.case_id,action:'calendar_event_deleted',entityType:'calendar_event',entityId:ev.id,summary:`Termin „${ev.title}“ gelöscht.`});res.status(204).end();}catch(error){next(error)}
});
app.get('/api/tasks', auth, async (req,res,next)=>{
  try {
    const organization=await organizationForUser(req.user.id);
    const mine=String(req.query.mine||'')==='1';
    const params=[]; let where='';
    if(organization){params.push(organization.id);where='t.organization_id=$1';if(mine){params.push(req.user.id);where+=' AND t.assigned_user_id=$2';}}
    else {params.push(req.user.id);where='t.organization_id IS NULL AND (t.created_by=$1 OR t.assigned_user_id=$1)';}
    const result=await pool.query(`SELECT t.*,c.title AS case_title,c.property_label,u.name AS assigned_name,creator.name AS creator_name
      FROM case_tasks t JOIN defect_cases c ON c.id=t.case_id
      LEFT JOIN users u ON u.id=t.assigned_user_id LEFT JOIN users creator ON creator.id=t.created_by
      WHERE ${where} ORDER BY CASE t.status WHEN 'open' THEN 0 ELSE 1 END,CASE t.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END,t.due_at NULLS LAST,t.created_at DESC`,params);
    const now=Date.now();
    res.json({tasks:result.rows.map(t=>({...t,overdue:t.status==='open'&&t.due_at&&new Date(t.due_at).getTime()<now})),organization:organization||null});
  } catch(error){next(error)}
});

app.get('/api/cases/:caseId/tasks', auth, async (req,res,next)=>{
  try {
    const accessible=await canAccessCase(req.user.id,req.params.caseId); if(!accessible) return res.status(404).json({error:'Vorgang nicht gefunden.'});
    const result=await pool.query(`SELECT t.*,u.name AS assigned_name FROM case_tasks t LEFT JOIN users u ON u.id=t.assigned_user_id WHERE t.case_id=$1 ORDER BY CASE t.status WHEN 'open' THEN 0 ELSE 1 END,t.due_at NULLS LAST,t.created_at DESC`,[req.params.caseId]);
    let members=[]; if(accessible.organization_id){const m=await pool.query(`SELECT u.id,u.name FROM organization_memberships om JOIN users u ON u.id=om.user_id WHERE om.organization_id=$1 AND COALESCE(om.active,true)=true ORDER BY u.name`,[accessible.organization_id]);members=m.rows;}
    res.json({tasks:result.rows,members,organizationId:accessible.organization_id||null});
  } catch(error){next(error)}
});

app.post('/api/cases/:caseId/tasks', auth, async (req,res,next)=>{
  try {
    const accessible=await canAccessCase(req.user.id,req.params.caseId); if(!accessible) return res.status(404).json({error:'Vorgang nicht gefunden.'});
    const title=cleanText(req.body.title,180); if(!title) return res.status(400).json({error:'Bitte gib einen Aufgabentitel an.'});
    const priority=['low','normal','high','urgent'].includes(req.body.priority)?req.body.priority:'normal';
    let assigned=req.body.assignedUserId||req.user.id;
    if(accessible.organization_id){const m=await pool.query(`SELECT 1 FROM organization_memberships WHERE organization_id=$1 AND user_id=$2 AND COALESCE(active,true)=true`,[accessible.organization_id,assigned]);if(!m.rowCount)return res.status(400).json({error:'Der gewählte Mitarbeiter gehört nicht aktiv zur Verwaltung.'});}
    else assigned=req.user.id;
    const taskId=id(); const result=await pool.query(`INSERT INTO case_tasks (id,organization_id,case_id,created_by,assigned_user_id,title,description,priority,due_at,remind_at) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) RETURNING *`,[taskId,accessible.organization_id||null,req.params.caseId,req.user.id,assigned,title,cleanText(req.body.description,1200),priority,req.body.dueAt||null,req.body.remindAt||null]);
    if(accessible.organization_id){await writeAudit({organizationId:accessible.organization_id,userId:req.user.id,caseId:req.params.caseId,action:'task_created',entityType:'task',entityId:taskId,summary:`Aufgabe „${title}“ erstellt.`});if(assigned!==req.user.id)await createNotification({userId:assigned,organizationId:accessible.organization_id,caseId:req.params.caseId,type:'task',title:'Neue Aufgabe für dich',body:title,link:'/app?view=tasks'});}
    res.status(201).json({task:result.rows[0]});
  } catch(error){next(error)}
});

app.patch('/api/tasks/:taskId', auth, async (req,res,next)=>{
  try {
    const r=await pool.query(`SELECT t.*,c.user_id AS case_owner FROM case_tasks t JOIN defect_cases c ON c.id=t.case_id WHERE t.id=$1`,[req.params.taskId]); if(!r.rowCount)return res.status(404).json({error:'Aufgabe nicht gefunden.'}); const task=r.rows[0];
    if(task.organization_id){const org=await organizationForUser(req.user.id);if(!org||org.id!==task.organization_id)return res.status(403).json({error:'Kein Zugriff.'});}
    else if(task.created_by!==req.user.id&&task.assigned_user_id!==req.user.id&&task.case_owner!==req.user.id)return res.status(403).json({error:'Kein Zugriff.'});
    const status=req.body.status==='done'?'done':req.body.status==='open'?'open':task.status;
    let assigned=req.body.assignedUserId===undefined?task.assigned_user_id:(req.body.assignedUserId||null);
    if(task.organization_id&&assigned){const m=await pool.query(`SELECT 1 FROM organization_memberships WHERE organization_id=$1 AND user_id=$2 AND COALESCE(active,true)=true`,[task.organization_id,assigned]);if(!m.rowCount)return res.status(400).json({error:'Ungültiger Mitarbeiter.'});}
    const result=await pool.query(`UPDATE case_tasks SET title=COALESCE($2,title),description=COALESCE($3,description),priority=COALESCE($4,priority),assigned_user_id=$5,due_at=$6,remind_at=$7,status=$8,completed_at=CASE WHEN $8='done' THEN COALESCE(completed_at,now()) ELSE NULL END,reminder_sent_at=CASE WHEN remind_at IS DISTINCT FROM $7 THEN NULL ELSE reminder_sent_at END,updated_at=now() WHERE id=$1 RETURNING *`,[task.id,cleanText(req.body.title,180),req.body.description===undefined?task.description:cleanText(req.body.description,1200),['low','normal','high','urgent'].includes(req.body.priority)?req.body.priority:task.priority,assigned,req.body.dueAt===undefined?task.due_at:(req.body.dueAt||null),req.body.remindAt===undefined?task.remind_at:(req.body.remindAt||null),status]);
    if(task.organization_id)await writeAudit({organizationId:task.organization_id,userId:req.user.id,caseId:task.case_id,action:status==='done'?'task_completed':'task_updated',entityType:'task',entityId:task.id,summary:status==='done'?`Aufgabe „${task.title}“ erledigt.`:`Aufgabe „${task.title}“ aktualisiert.`});
    res.json({task:result.rows[0]});
  } catch(error){next(error)}
});
app.get('/api/notifications', auth, async (req,res,next)=>{
  try {
    const result=await pool.query(`SELECT * FROM notifications WHERE user_id=$1 ORDER BY created_at DESC LIMIT 100`,[req.user.id]);
    res.json({notifications:result.rows,unread:result.rows.filter(x=>!x.read_at).length});
  } catch(error){next(error);}
});

app.post('/api/notifications/read-all', auth, async (req,res,next)=>{
  try { await pool.query('UPDATE notifications SET read_at=COALESCE(read_at,now()) WHERE user_id=$1',[req.user.id]); res.json({ok:true}); }
  catch(error){next(error);}
});

app.post('/api/notifications/:notificationId/read', auth, async (req,res,next)=>{
  try {
    const result=await pool.query('UPDATE notifications SET read_at=COALESCE(read_at,now()) WHERE id=$1 AND user_id=$2 RETURNING *',[req.params.notificationId,req.user.id]);
    if(!result.rowCount) return res.status(404).json({error:'Benachrichtigung nicht gefunden.'});
    res.json({notification:result.rows[0]});
  } catch(error){next(error);}
});

app.get('/api/audit', auth, async (req,res,next)=>{
  try {
    const organization=await organizationForUser(req.user.id);
    if(!organization) return res.status(403).json({error:'Das Aktivitätsprotokoll ist im Verwaltungsbereich verfügbar.'});
    const result=await pool.query(`SELECT al.*,u.name AS actor_name FROM audit_logs al LEFT JOIN users u ON u.id=al.user_id WHERE al.organization_id=$1 ORDER BY al.created_at DESC LIMIT 250`,[organization.id]);
    res.json({logs:result.rows});
  } catch(error){next(error);}
});

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
      pool.query(`SELECT c.*,uc.role,uc.is_primary, EXISTS(SELECT 1 FROM tenant_links tl WHERE tl.contact_id=c.id AND tl.unit_id=uc.unit_id AND tl.status='active') AS digitally_linked, (SELECT usr.email FROM tenant_links tl JOIN users usr ON usr.id=tl.user_id WHERE tl.contact_id=c.id AND tl.unit_id=uc.unit_id AND tl.status='active' LIMIT 1) AS linked_account_email FROM unit_contacts uc JOIN contacts c ON c.id=uc.contact_id WHERE uc.unit_id=$1 ORDER BY uc.is_primary DESC,c.name`, [req.params.unitId]),
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
    const ownOrganization = await organizationForUser(req.user.id);
    let destination = null;
    const destinationLinkId = cleanText(req.body.destinationLinkId, 80);
    if (destinationLinkId && !ownOrganization) {
      const destinationResult = await client.query(`SELECT tl.*,p.name AS property_name,p.street,p.postal_code,p.city,p.allow_tenant_submissions,u.label AS unit_label,o.name AS organization_name
        FROM tenant_links tl JOIN properties p ON p.id=tl.property_id JOIN units u ON u.id=tl.unit_id JOIN organizations o ON o.id=tl.organization_id
        WHERE tl.id=$1 AND tl.user_id=$2 AND tl.status='active'`, [destinationLinkId, req.user.id]);
      if (!destinationResult.rowCount) { await client.query('ROLLBACK'); return res.status(400).json({error:'Die ausgewählte Hausverwaltungs-Verknüpfung ist nicht gültig.'}); }
      destination=destinationResult.rows[0];
      if (!destination.allow_tenant_submissions) { await client.query('ROLLBACK'); return res.status(403).json({error:'Diese Hausverwaltung nimmt für dieses Objekt derzeit keine digitalen Mängelmeldungen über MängelFix an.'}); }
    }
    const organizationId = destination?.organization_id || ownOrganization?.id || null;
    const propertyLabel = destination ? [destination.property_name, destination.unit_label].filter(Boolean).join(' · ') : cleanText(req.body.propertyLabel, 200);
    const recipientName = destination?.organization_name || cleanText(req.body.recipientName, 160);
    const result = await client.query(
      `INSERT INTO defect_cases
       (id,user_id,organization_id,property_id,unit_id,tenant_link_id,submitted_by_tenant,title,category,description,property_label,location_label,discovered_on,recipient_name,recipient_email,recipient_address,deadline_on,status)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,'draft')
       RETURNING *`,
      [
        caseId,
        req.user.id,
        organizationId,
        destination?.property_id || null,
        destination?.unit_id || null,
        destination?.id || null,
        Boolean(destination),
        title,
        cleanText(req.body.category, 80) || 'Sonstiges',
        description,
        propertyLabel,
        cleanText(req.body.locationLabel, 120),
        req.body.discoveredOn || null,
        recipientName,
        cleanText(req.body.recipientEmail, 254)?.toLowerCase(),
        cleanText(req.body.recipientAddress, 500),
        req.body.deadlineOn || null
      ]
    );
    if (destination) {
      await client.query(`UPDATE defect_cases SET status='received' WHERE id=$1`,[caseId]);
      result.rows[0].status='received';
      await notifyOrganization(destination.organization_id,{caseId,type:'tenant_case',title:'Neue Mängelmeldung vom Mieter',body:title,link:`/app?case=${caseId}`},req.user.id);
      await writeAudit({organizationId:destination.organization_id,userId:req.user.id,caseId,action:'tenant_submitted',entityType:'case',entityId:caseId,summary:`Mieter hat den Mangel „${title}“ digital übermittelt.`});
    }
    await client.query(
      'INSERT INTO case_events (id, case_id, user_id, event_type, note) VALUES ($1,$2,$3,$4,$5)',
      [id(), caseId, req.user.id, 'created', destination ? `Mangel wurde vom Mieter digital an ${destination.organization_name} übermittelt.` : 'Mangel wurde erfasst.']
    );
    await client.query('COMMIT');
    if (destination) { try { await notifyOrganization(destination.organization_id,`Neuer Mangel: ${title}`,`${req.user.name} hat einen neuen Mangel für ${destination.property_name} · ${destination.unit_label} digital übermittelt.`,caseId); } catch(mailError){ console.error('New case notification failed',mailError); } }
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
    const viewerOrganization = await organizationForUser(req.user.id);
    const viewerIsOrganization = Boolean(viewerOrganization && viewerOrganization.id === result.rows[0].organization_id);
    const [events, attachments, messages] = await Promise.all([
      pool.query(`SELECT e.*, u.name AS actor_name FROM case_events e LEFT JOIN users u ON u.id=e.user_id WHERE e.case_id=$1 AND ($2::boolean=true OR e.visibility='shared') ORDER BY e.created_at DESC`, [req.params.caseId, viewerIsOrganization]),
      pool.query('SELECT id, original_name, mime_type, size_bytes, created_at FROM attachments WHERE case_id = $1 ORDER BY created_at', [req.params.caseId]),
      pool.query('SELECT m.*,u.name AS actor_name FROM case_messages m JOIN users u ON u.id=m.user_id WHERE m.case_id=$1 ORDER BY m.created_at', [req.params.caseId])
    ]);
    res.json({ case: result.rows[0], events: events.rows, attachments: attachments.rows, messages: messages.rows, viewerRole: viewerIsOrganization ? 'management' : 'tenant' });
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
        'INSERT INTO case_events (id, case_id, user_id, event_type, note, visibility) VALUES ($1,$2,$3,$4,$5,'shared')',
        [id(), req.params.caseId, req.user.id, 'status', `Status geändert: ${nextStatus}`]
      );
      if (old.submitted_by_tenant) {
        const owner=await tenantOwnerForCase(req.params.caseId);
        if(owner && owner.id!==req.user.id){ try { await sendAppMail({to:owner.email,subject:`Status aktualisiert: ${old.title}`,heading:'Deine Mängelmeldung wurde aktualisiert',text:`Der Status von „${old.title}“ wurde geändert. Neuer Status: ${nextStatus}.`,buttonLabel:'Vorgang öffnen',buttonUrl:`${appOrigin}/app?case=${req.params.caseId}`}); } catch(mailError){console.error('Status mail failed',mailError);} }
      }
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
    const viewerOrganization=await organizationForUser(req.user.id);
    const isManagement=Boolean(viewerOrganization && viewerOrganization.id===accessible.organization_id);
    const visibility=isManagement ? 'internal' : 'shared';
    const result = await pool.query(
      'INSERT INTO case_events (id, case_id, user_id, event_type, note, visibility) VALUES ($1,$2,$3,$4,$5,$6) RETURNING *',
      [id(), req.params.caseId, req.user.id, 'note', note, visibility]
    );
    await pool.query('UPDATE defect_cases SET updated_at=now() WHERE id=$1', [req.params.caseId]);
    if (accessible.organization_id) await writeAudit({organizationId:accessible.organization_id,userId:req.user.id,caseId:req.params.caseId,action:'note_added',entityType:'case',entityId:req.params.caseId,summary:'Interne Notiz zum Vorgang ergänzt.'});
    res.status(201).json({ event: result.rows[0] });
  } catch (error) {
    next(error);
  }
});


app.post('/api/cases/:caseId/messages', auth, async (req,res,next)=>{
  try {
    const accessible=await canAccessCase(req.user.id,req.params.caseId);
    if(!accessible) return res.status(404).json({error:'Mangel nicht gefunden.'});
    if(!accessible.submitted_by_tenant) return res.status(400).json({error:'Gemeinsame Nachrichten sind nur bei digital verbundenen Mietervorgängen verfügbar.'});
    const message=cleanText(req.body.message,4000);
    if(!message) return res.status(400).json({error:'Nachricht darf nicht leer sein.'});
    const result=await pool.query(`INSERT INTO case_messages (id,case_id,user_id,message) VALUES ($1,$2,$3,$4) RETURNING *`,[id(),req.params.caseId,req.user.id,message]);
    await pool.query('UPDATE defect_cases SET updated_at=now() WHERE id=$1',[req.params.caseId]);
    const viewerOrganization=await organizationForUser(req.user.id);
    const fromManagement=Boolean(viewerOrganization && viewerOrganization.id===accessible.organization_id);
    try {
      if(fromManagement){
        const owner=await tenantOwnerForCase(req.params.caseId);
        if(owner) await sendAppMail({to:owner.email,subject:`Neue Nachricht zu: ${accessible.title}`,heading:'Neue Nachricht deiner Hausverwaltung',text:message,buttonLabel:'Nachricht öffnen',buttonUrl:`${appOrigin}/app?case=${req.params.caseId}`});
      } else {
        await notifyOrganization(accessible.organization_id,`Neue Mieternachricht: ${accessible.title}`,`${req.user.name}: ${message}`,req.params.caseId);
      }
    } catch(mailError){console.error('Message mail failed',mailError);}
    res.status(201).json({message:result.rows[0]});
  } catch(error){next(error);}
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
    const forceDownload = String(req.query.download || '') === '1';
    res.setHeader('Content-Disposition', `${forceDownload ? 'attachment' : 'inline'}; filename="maengelfix-${item.id}.pdf"`);
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

const indexHtml = fs.readFileSync(path.join(publicDir, 'index.html'), 'utf8');

app.use(express.static(publicDir, { index: false, maxAge: production ? '1h' : 0 }));
app.use((req, res, next) => {
  if (req.method !== 'GET' || req.path.startsWith('/api/')) return next();
  res.status(200)
    .set({
      'Content-Type': 'text/html; charset=utf-8',
      'Content-Disposition': 'inline',
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff'
    })
    .send(indexHtml);
});

app.use((error, _req, res, _next) => {
  console.error(error);
  if (error instanceof multer.MulterError) return res.status(400).json({ error: error.message });
  res.status(500).json({ error: 'Etwas ist schiefgelaufen.' });
});


async function processTaskReminders(){
  try{
    const due=await pool.query(`SELECT t.*,u.email,u.name,c.title AS case_title FROM case_tasks t LEFT JOIN users u ON u.id=t.assigned_user_id JOIN defect_cases c ON c.id=t.case_id WHERE t.status='open' AND t.remind_at IS NOT NULL AND t.remind_at<=now() AND t.reminder_sent_at IS NULL LIMIT 100`);
    for(const task of due.rows){
      if(task.assigned_user_id) await createNotification({userId:task.assigned_user_id,organizationId:task.organization_id,caseId:task.case_id,type:'task_reminder',title:'Wiedervorlage fällig',body:task.title,link:'/app?view=tasks'});
      if(mailer&&task.email) try{await sendAppMail({to:task.email,subject:'MängelFix Wiedervorlage',heading:'Eine Aufgabe ist fällig',text:`${task.title}\nVorgang: ${task.case_title}`,buttonLabel:'Aufgaben öffnen',buttonUrl:`${appOrigin}/app?view=tasks`});}catch(e){console.error('Task reminder mail failed',e)}
      await pool.query('UPDATE case_tasks SET reminder_sent_at=now() WHERE id=$1 AND reminder_sent_at IS NULL',[task.id]);
    }
  }catch(error){console.error('Task reminder worker failed',error)}
}
setTimeout(processTaskReminders,15000);
setInterval(processTaskReminders,15*60*1000);


async function processCalendarReminders(){
  try{const due=await pool.query(`SELECT ce.*,u.email,c.title AS case_title FROM calendar_events ce LEFT JOIN users u ON u.id=ce.assigned_user_id LEFT JOIN defect_cases c ON c.id=ce.case_id WHERE ce.status IN ('planned','confirmed') AND ce.reminder_at IS NOT NULL AND ce.reminder_at<=now() AND ce.reminder_sent_at IS NULL LIMIT 100`);for(const ev of due.rows){if(ev.assigned_user_id)await createNotification({userId:ev.assigned_user_id,organizationId:ev.organization_id,caseId:ev.case_id,type:'appointment_reminder',title:'Termin-Erinnerung',body:`${ev.title} · ${new Date(ev.starts_at).toLocaleString('de-DE')}`,link:'/app?view=calendar'});if(mailer&&ev.email)try{await sendAppMail({to:ev.email,subject:'MängelFix Termin-Erinnerung',heading:'Termin steht an',text:`${ev.title}\n${new Date(ev.starts_at).toLocaleString('de-DE')}${ev.case_title?`\nVorgang: ${ev.case_title}`:''}`,buttonLabel:'Kalender öffnen',buttonUrl:`${appOrigin}/app?view=calendar`})}catch(e){console.error('Calendar reminder mail failed',e)}await pool.query('UPDATE calendar_events SET reminder_sent_at=now() WHERE id=$1 AND reminder_sent_at IS NULL',[ev.id]);}}catch(error){console.error('Calendar reminder worker failed',error)}}
setTimeout(processCalendarReminders,20000);setInterval(processCalendarReminders,15*60*1000);

app.listen(port, '0.0.0.0', () => {
  console.log(`MängelFix läuft auf Port ${port}`);
});
