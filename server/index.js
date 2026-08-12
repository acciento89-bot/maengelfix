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
  const hash = tokenHash(token);
  await pool.query(
    `INSERT INTO sessions (token_hash, user_id, expires_at)
     VALUES ($1, $2, now() + interval '30 days')`,
    [hash, userId]
  );
  setSessionCookie(res, token);
}

async function auth(req, res, next) {
  try {
    const token = req.cookies[cookieName];
    if (!token) return res.status(401).json({ error: 'Bitte melde dich an.' });
    const result = await pool.query(
      `SELECT u.id, u.name, u.email
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

function cleanText(value, max = 1000) {
  if (value === null || value === undefined) return null;
  return String(value).trim().slice(0, max);
}

const allowedStatuses = new Set(['draft', 'sent', 'reply', 'in_progress', 'resolved']);

app.get('/api/health', async (_req, res) => {
  await pool.query('SELECT 1');
  res.json({ ok: true, service: 'maengelfix', version: '0.1.0' });
});

app.post('/api/auth/register', async (req, res, next) => {
  try {
    const name = cleanText(req.body.name, 120);
    const email = cleanText(req.body.email, 254)?.toLowerCase();
    const password = String(req.body.password || '');
    if (!name || !email || password.length < 8) {
      return res.status(400).json({ error: 'Name, gültige E-Mail und mindestens 8 Zeichen Passwort sind erforderlich.' });
    }
    const existing = await pool.query('SELECT 1 FROM users WHERE email = $1', [email]);
    if (existing.rowCount) return res.status(409).json({ error: 'Für diese E-Mail existiert bereits ein Konto.' });
    const credentials = await makePassword(password);
    const user = { id: id(), name, email };
    await pool.query(
      'INSERT INTO users (id, name, email, password_salt, password_hash) VALUES ($1,$2,$3,$4,$5)',
      [user.id, user.name, user.email, credentials.salt, credentials.hash]
    );
    await createSession(user.id, res);
    res.status(201).json({ user });
  } catch (error) {
    next(error);
  }
});

app.post('/api/auth/login', async (req, res, next) => {
  try {
    const email = cleanText(req.body.email, 254)?.toLowerCase();
    const password = String(req.body.password || '');
    const result = await pool.query(
      'SELECT id, name, email, password_salt, password_hash FROM users WHERE email = $1',
      [email]
    );
    const row = result.rows[0];
    if (!row || !(await verifyPassword(password, row.password_salt, row.password_hash))) {
      return res.status(401).json({ error: 'E-Mail oder Passwort ist nicht korrekt.' });
    }
    await createSession(row.id, res);
    res.json({ user: { id: row.id, name: row.name, email: row.email } });
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

app.get('/api/me', auth, (req, res) => res.json({ user: req.user }));

app.get('/api/cases', auth, async (req, res, next) => {
  try {
    const result = await pool.query(
      `SELECT c.*,
        (SELECT count(*)::int FROM attachments a WHERE a.case_id = c.id) AS attachment_count
       FROM defect_cases c
       WHERE c.user_id = $1
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
       (id,user_id,title,category,description,property_label,location_label,discovered_on,recipient_name,recipient_email,recipient_address,deadline_on,status)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,'draft')
       RETURNING *`,
      [
        caseId,
        req.user.id,
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
    const result = await pool.query('SELECT * FROM defect_cases WHERE id = $1 AND user_id = $2', [req.params.caseId, req.user.id]);
    if (!result.rowCount) return res.status(404).json({ error: 'Mangel nicht gefunden.' });
    const [events, attachments] = await Promise.all([
      pool.query('SELECT * FROM case_events WHERE case_id = $1 AND user_id = $2 ORDER BY created_at DESC', [req.params.caseId, req.user.id]),
      pool.query('SELECT id, original_name, mime_type, size_bytes, created_at FROM attachments WHERE case_id = $1 AND user_id = $2 ORDER BY created_at', [req.params.caseId, req.user.id])
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
    const current = await pool.query('SELECT * FROM defect_cases WHERE id=$1 AND user_id=$2', [req.params.caseId, req.user.id]);
    if (!current.rowCount) return res.status(404).json({ error: 'Mangel nicht gefunden.' });
    const old = current.rows[0];
    const nextStatus = status || old.status;
    const result = await pool.query(
      `UPDATE defect_cases SET
       title=$3, category=$4, description=$5, property_label=$6, location_label=$7,
       discovered_on=$8, recipient_name=$9, recipient_email=$10, recipient_address=$11,
       deadline_on=$12, status=$13, updated_at=now()
       WHERE id=$1 AND user_id=$2 RETURNING *`,
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
    const owner = await pool.query('SELECT 1 FROM defect_cases WHERE id=$1 AND user_id=$2', [req.params.caseId, req.user.id]);
    if (!owner.rowCount) return res.status(404).json({ error: 'Mangel nicht gefunden.' });
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
    const owner = await pool.query('SELECT 1 FROM defect_cases WHERE id=$1 AND user_id=$2', [req.params.caseId, req.user.id]);
    if (!owner.rowCount) return res.status(404).json({ error: 'Mangel nicht gefunden.' });
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
    const result = await pool.query('SELECT * FROM attachments WHERE id=$1 AND user_id=$2', [req.params.attachmentId, req.user.id]);
    if (!result.rowCount) return res.status(404).end();
    const item = result.rows[0];
    res.type(item.mime_type).sendFile(path.join(uploadDir, item.stored_name));
  } catch (error) {
    next(error);
  }
});

app.get('/api/cases/:caseId/pdf', auth, async (req, res, next) => {
  try {
    const result = await pool.query('SELECT * FROM defect_cases WHERE id=$1 AND user_id=$2', [req.params.caseId, req.user.id]);
    if (!result.rowCount) return res.status(404).json({ error: 'Mangel nicht gefunden.' });
    const item = result.rows[0];
    const doc = new PDFDocument({ size: 'A4', margin: 56, info: { Title: `MängelFix – ${item.title}` } });
    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', `attachment; filename="maengelfix-${item.id}.pdf"`);
    doc.pipe(res);

    doc.fontSize(22).text('Mängelanzeige / Dokumentation', { align: 'left' });
    doc.moveDown(0.5).fontSize(10).fillColor('#555').text('Erstellt mit MängelFix');
    doc.fillColor('#000').moveDown(1.4);

    if (item.recipient_name || item.recipient_address) {
      doc.fontSize(11).text('Empfänger', { underline: true });
      if (item.recipient_name) doc.text(item.recipient_name);
      if (item.recipient_address) doc.text(item.recipient_address);
      if (item.recipient_email) doc.text(item.recipient_email);
      doc.moveDown();
    }

    doc.fontSize(14).text(item.title);
    doc.moveDown(0.5).fontSize(11);
    if (item.property_label) doc.text(`Objekt: ${item.property_label}`);
    if (item.location_label) doc.text(`Ort / Raum: ${item.location_label}`);
    if (item.category) doc.text(`Kategorie: ${item.category}`);
    if (item.discovered_on) doc.text(`Festgestellt am: ${new Date(item.discovered_on).toLocaleDateString('de-DE')}`);
    doc.moveDown();
    doc.text('Beschreibung', { underline: true });
    doc.moveDown(0.3).text(item.description, { lineGap: 3 });
    doc.moveDown();

    doc.text('Mitteilung', { underline: true });
    doc.moveDown(0.3).text('Hiermit teile ich den oben beschriebenen Mangel mit und bitte um Prüfung sowie Rückmeldung.');
    if (item.deadline_on) {
      doc.text(`Als gewünschtes Rückmeldedatum habe ich den ${new Date(item.deadline_on).toLocaleDateString('de-DE')} vermerkt.`);
    }
    doc.moveDown(2);
    doc.fontSize(9).fillColor('#666').text('Hinweis: MängelFix unterstützt bei Dokumentation und Organisation. Das Dokument stellt keine Rechtsberatung dar.');
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
