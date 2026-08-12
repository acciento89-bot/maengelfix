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
    const [caseResult, attachmentResult] = await Promise.all([
      pool.query('SELECT * FROM defect_cases WHERE id=$1 AND user_id=$2', [req.params.caseId, req.user.id]),
      pool.query('SELECT * FROM attachments WHERE case_id=$1 AND user_id=$2 ORDER BY created_at', [req.params.caseId, req.user.id])
    ]);
    if (!caseResult.rowCount) return res.status(404).json({ error: 'Mangel nicht gefunden.' });

    const item = caseResult.rows[0];
    const attachments = attachmentResult.rows;
    const doc = new PDFDocument({
      size: 'A4',
      margins: { top: 54, right: 52, bottom: 58, left: 52 },
      info: { Title: `MängelFix – ${item.title}`, Author: req.user.name || 'MängelFix' }
    });

    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', `attachment; filename="maengelfix-${item.id}.pdf"`);
    doc.pipe(res);

    const C = {
      ink: '#18212B',
      muted: '#6F7A86',
      line: '#DFE4E8',
      panel: '#F5F7F9',
      blue: '#2457D6',
      blueSoft: '#EAF0FF',
      amber: '#E4A11B',
      white: '#FFFFFF'
    };
    const pageW = doc.page.width;
    const left = 52;
    const right = pageW - 52;
    const width = right - left;
    const date = value => value ? new Date(value).toLocaleDateString('de-DE') : '—';
    const statusLabels = {
      draft: 'Entwurf',
      sent: 'Versendet',
      reply: 'Rückmeldung',
      in_progress: 'In Bearbeitung',
      resolved: 'Erledigt'
    };
    const shortId = String(item.id).split('-')[0].toUpperCase();

    const addFooter = () => {
      const y = doc.page.height - 35;
      doc.save();
      doc.moveTo(left, y - 10).lineTo(right, y - 10).strokeColor(C.line).lineWidth(0.7).stroke();
      doc.font('Helvetica').fontSize(8).fillColor(C.muted)
        .text('MängelFix · Dokumentation & Fristen im Blick', left, y, { width: width / 2, align: 'left' });
      doc.text(`Vorgang ${shortId}`, left + width / 2, y, { width: width / 2, align: 'right' });
      doc.restore();
    };
    const ensureSpace = amount => {
      if (doc.y + amount > doc.page.height - 72) {
        addFooter();
        doc.addPage();
        doc.y = 54;
      }
    };
    const sectionLabel = text => {
      doc.font('Helvetica-Bold').fontSize(9).fillColor(C.blue).text(text.toUpperCase(), { characterSpacing: 1.05 });
      doc.moveDown(0.45);
    };
    const infoBox = (x, y, w, label, value) => {
      doc.roundedRect(x, y, w, 58, 7).fill(C.panel);
      doc.font('Helvetica').fontSize(8).fillColor(C.muted).text(label, x + 12, y + 11, { width: w - 24 });
      doc.font('Helvetica-Bold').fontSize(10.5).fillColor(C.ink).text(value || '—', x + 12, y + 28, { width: w - 24, ellipsis: true });
    };

    // Headerband
    doc.rect(0, 0, pageW, 124).fill(C.ink);
    doc.roundedRect(left, 34, 34, 34, 7).fill(C.white);
    doc.font('Helvetica-Bold').fontSize(15).fillColor(C.ink).text('MF', left + 6, 44, { width: 24, align: 'center' });
    doc.font('Helvetica-Bold').fontSize(18).fillColor(C.white).text('MängelFix', left + 46, 38);
    doc.font('Helvetica').fontSize(8.5).fillColor('#B8C0C8').text('MÄNGELDOKUMENTATION', left + 46, 61, { characterSpacing: 1.2 });

    doc.font('Helvetica').fontSize(8).fillColor('#B8C0C8').text('VORGANG', right - 180, 38, { width: 180, align: 'right' });
    doc.font('Helvetica-Bold').fontSize(11).fillColor(C.white).text(shortId, right - 180, 52, { width: 180, align: 'right' });
    doc.font('Helvetica').fontSize(8).fillColor('#B8C0C8').text(`Erstellt am ${new Date().toLocaleDateString('de-DE')}`, right - 180, 70, { width: 180, align: 'right' });

    doc.y = 151;
    doc.font('Helvetica-Bold').fontSize(9).fillColor(C.blue).text(item.category || 'Mangel', { characterSpacing: .8 });
    doc.moveDown(0.35);
    doc.font('Helvetica-Bold').fontSize(25).fillColor(C.ink).text(item.title, { width });
    doc.moveDown(0.75);

    const chipY = doc.y;
    doc.roundedRect(left, chipY, 94, 24, 5).fill(C.blueSoft);
    doc.font('Helvetica-Bold').fontSize(8).fillColor(C.blue).text((statusLabels[item.status] || item.status).toUpperCase(), left + 10, chipY + 8, { width: 74, align: 'center' });
    doc.font('Helvetica').fontSize(9).fillColor(C.muted).text(`Festgestellt: ${date(item.discovered_on)}`, left + 108, chipY + 7);
    doc.y = chipY + 42;

    // Faktenleiste
    const gap = 8;
    const boxW = (width - gap) / 2;
    let y = doc.y;
    infoBox(left, y, boxW, 'Objekt', item.property_label);
    infoBox(left + boxW + gap, y, boxW, 'Raum / Ort', item.location_label);
    y += 66;
    infoBox(left, y, boxW, 'Gewünschte Rückmeldung bis', date(item.deadline_on));
    infoBox(left + boxW + gap, y, boxW, 'Empfänger', item.recipient_name);
    doc.y = y + 82;

    // Empfängerblock
    if (item.recipient_name || item.recipient_address || item.recipient_email) {
      sectionLabel('Empfänger');
      const recipientY = doc.y;
      const recipientLines = [item.recipient_name, item.recipient_address, item.recipient_email].filter(Boolean).join('\n');
      const recHeight = Math.max(64, doc.heightOfString(recipientLines, { width: width - 28, lineGap: 2 }) + 28);
      doc.roundedRect(left, recipientY, width, recHeight, 7).strokeColor(C.line).lineWidth(0.9).stroke();
      doc.font('Helvetica').fontSize(10.5).fillColor(C.ink).text(recipientLines, left + 14, recipientY + 14, { width: width - 28, lineGap: 2 });
      doc.y = recipientY + recHeight + 22;
    }

    ensureSpace(120);
    sectionLabel('Beschreibung');
    const descY = doc.y;
    const descHeight = Math.max(84, doc.heightOfString(item.description, { width: width - 30, lineGap: 4 }) + 30);
    doc.roundedRect(left, descY, width, descHeight, 7).fill(C.panel);
    doc.font('Helvetica').fontSize(11).fillColor(C.ink).text(item.description, left + 15, descY + 15, { width: width - 30, lineGap: 4 });
    doc.y = descY + descHeight + 24;

    ensureSpace(120);
    sectionLabel('Mitteilung');
    doc.font('Helvetica').fontSize(10.7).fillColor(C.ink)
      .text('Hiermit zeige ich den oben dokumentierten Mangel an und bitte um Prüfung sowie eine Rückmeldung zum weiteren Vorgehen.', { width, lineGap: 4 });
    if (item.deadline_on) {
      doc.moveDown(0.55).font('Helvetica-Bold').fillColor(C.ink)
        .text(`Gewünschtes Rückmeldedatum: ${date(item.deadline_on)}`, { width });
    }
    doc.moveDown(1.1);

    // Fotos als Belegübersicht
    const embeddable = attachments.filter(a => /^image\/(jpeg|png)$/.test(a.mime_type));
    if (embeddable.length) {
      ensureSpace(220);
      sectionLabel(`Fotobelege (${embeddable.length})`);
      const imageGap = 10;
      const imageW = (width - imageGap) / 2;
      const imageH = 148;
      for (let i = 0; i < embeddable.length; i += 2) {
        ensureSpace(imageH + 34);
        const row = embeddable.slice(i, i + 2);
        const rowY = doc.y;
        row.forEach((attachment, index) => {
          const x = left + index * (imageW + imageGap);
          doc.roundedRect(x, rowY, imageW, imageH + 26, 7).strokeColor(C.line).lineWidth(.8).stroke();
          try {
            doc.image(path.join(uploadDir, attachment.stored_name), x + 6, rowY + 6, {
              fit: [imageW - 12, imageH - 12],
              align: 'center',
              valign: 'center'
            });
          } catch {
            doc.font('Helvetica').fontSize(8).fillColor(C.muted).text('Bild konnte nicht eingebettet werden.', x + 10, rowY + 62, { width: imageW - 20, align: 'center' });
          }
          doc.font('Helvetica').fontSize(7.5).fillColor(C.muted).text(attachment.original_name || 'Fotobeleg', x + 8, rowY + imageH + 8, { width: imageW - 16, ellipsis: true });
        });
        doc.y = rowY + imageH + 38;
      }
    }

    ensureSpace(78);
    doc.moveDown(0.6);
    doc.roundedRect(left, doc.y, width, 48, 7).fill('#FFF7E8');
    doc.font('Helvetica-Bold').fontSize(8).fillColor('#8A5A09').text('HINWEIS', left + 12, doc.y + 10);
    doc.font('Helvetica').fontSize(8.5).fillColor('#765D32')
      .text('MängelFix unterstützt bei Dokumentation und Organisation. Dieses Dokument ersetzt keine Rechtsberatung.', left + 12, doc.y + 24, { width: width - 24 });

    addFooter();
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
