from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
server = root / 'server' / 'index.js'
package = root / 'server' / 'package.json'

text = server.read_text()

import_line = "import { AppStoreServerAPIClient, Environment } from '@apple/app-store-server-library';\n"
if import_line not in text:
    anchor = "import nodemailer from 'nodemailer';\n"
    if anchor not in text:
        raise SystemExit('nodemailer import anchor not found')
    text = text.replace(anchor, anchor + import_line, 1)

constants = r'''
const appleBundleId = process.env.APPLE_APP_BUNDLE_ID || 'com.kamilunavo.maengelfix';
const appleIssuerId = process.env.APPLE_IAP_ISSUER_ID || '';
const appleKeyId = process.env.APPLE_IAP_KEY_ID || '';
const applePrivateKey = String(process.env.APPLE_IAP_PRIVATE_KEY || '').replace(/\\n/g, '\n');
const appleBillingConfigured = Boolean(appleIssuerId && appleKeyId && applePrivateKey);
const appleProductIds = new Set([
  'com.kamilunavo.maengelfix.privatepro.monthly',
  'com.kamilunavo.maengelfix.privatepro.yearly'
]);
'''
if 'const appleBundleId =' not in text:
    anchor = "const appOrigin = process.env.APP_ORIGIN || 'https://maengelfix.kamilunavo.com';\n"
    if anchor not in text:
        raise SystemExit('appOrigin anchor not found')
    text = text.replace(anchor, anchor + constants, 1)

helpers = r'''
function decodeAppleJwsPayload(jws) {
  const parts = String(jws || '').split('.');
  if (parts.length !== 3) throw new Error('Ungültige Apple-JWS-Antwort.');
  return JSON.parse(Buffer.from(parts[1], 'base64url').toString('utf8'));
}

function appleClient(environment) {
  if (!appleBillingConfigured) throw new Error('Apple In-App Purchase ist serverseitig noch nicht konfiguriert.');
  return new AppStoreServerAPIClient(applePrivateKey, appleKeyId, appleIssuerId, appleBundleId, environment);
}

async function fetchAppleTransaction(transactionId) {
  let lastError = null;
  for (const environment of [Environment.PRODUCTION, Environment.SANDBOX]) {
    try {
      const response = await appleClient(environment).getTransactionInfo(transactionId);
      const transaction = decodeAppleJwsPayload(response.signedTransactionInfo);
      return { transaction, environment: environment === Environment.PRODUCTION ? 'Production' : 'Sandbox' };
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError || new Error('Apple-Transaktion konnte nicht geladen werden.');
}

async function applyAppleTransaction(transaction, expectedUserId = null) {
  if (transaction.bundleId !== appleBundleId) throw new Error('Apple-Transaktion gehört nicht zu MängelFix.');
  if (!appleProductIds.has(transaction.productId)) throw new Error('Unbekanntes MängelFix Apple-Produkt.');
  const userId = String(transaction.appAccountToken || '').toLowerCase();
  if (!userId) throw new Error('Apple-Transaktion enthält keine MängelFix-Kontoverknüpfung.');
  if (expectedUserId && userId !== String(expectedUserId).toLowerCase()) throw new Error('Apple-Transaktion gehört zu einem anderen MängelFix-Konto.');

  const expiresMs = Number(transaction.expiresDate || 0);
  const active = !transaction.revocationDate && expiresMs > Date.now();
  const current = await pool.query('SELECT * FROM users WHERE lower(id)=lower($1)', [userId]);
  if (!current.rowCount) throw new Error('Verknüpftes MängelFix-Konto wurde nicht gefunden.');
  const existing = current.rows[0];

  // Niemals ein parallel aktives Stripe-Abo durch eine Apple-Statusänderung herabstufen.
  if (existing.subscription_provider === 'stripe' && existing.plan_code === 'private_pro' && ['active','trialing'].includes(existing.subscription_status)) {
    return publicUser(existing);
  }

  const periodEnd = expiresMs ? new Date(expiresMs) : null;
  const result = await pool.query(
    `UPDATE users SET
       plan_code=$2,
       subscription_status=$3,
       subscription_provider='apple',
       subscription_customer_id=$4,
       subscription_id=$5,
       subscription_current_period_end=$6
     WHERE id=$1
     RETURNING id,name,email,street,postal_code,city,country,phone,email_verified_at,plan_code,subscription_status,subscription_current_period_end,onboarding_completed_at,onboarding_use_case`,
    [
      existing.id,
      active ? 'private_pro' : 'private_free',
      active ? 'active' : 'inactive',
      transaction.appAccountToken || existing.id,
      transaction.originalTransactionId || transaction.transactionId,
      periodEnd
    ]
  );

  await pool.query(
    `INSERT INTO billing_events (id,provider,provider_event_id,user_id,event_type,payload)
     VALUES ($1,'apple',$2,$3,$4,$5::jsonb)
     ON CONFLICT (provider_event_id) DO NOTHING`,
    [id(), String(transaction.transactionId), existing.id, active ? 'subscription_active' : 'subscription_inactive', JSON.stringify(transaction)]
  );
  return publicUser(result.rows[0]);
}
'''
if 'function decodeAppleJwsPayload' not in text:
    anchor = "function id() {\n"
    if anchor not in text:
        raise SystemExit('id() anchor not found')
    text = text.replace(anchor, helpers + "\n" + anchor, 1)

routes = r'''
app.post('/api/billing/apple/verify', auth, async (req, res, next) => {
  try {
    if (!appleBillingConfigured) return res.status(503).json({error:'Apple In-App Purchase ist serverseitig noch nicht konfiguriert.',code:'APPLE_IAP_NOT_CONFIGURED'});
    const transactionId = cleanText(req.body.transactionId, 80);
    if (!transactionId) return res.status(400).json({error:'Apple-Transaktions-ID fehlt.'});
    const { transaction, environment } = await fetchAppleTransaction(transactionId);
    const user = await applyAppleTransaction(transaction, req.user.id);
    res.json({user,productId:transaction.productId,expiresAt:transaction.expiresDate || null,environment});
  } catch (error) { next(error); }
});

app.post('/api/billing/apple/notifications', async (req, res) => {
  try {
    if (!appleBillingConfigured) return res.status(503).json({ok:false});
    const outer = decodeAppleJwsPayload(req.body?.signedPayload);
    const signedTransactionInfo = outer?.data?.signedTransactionInfo;
    if (!signedTransactionInfo) return res.json({ok:true,ignored:true});
    const hinted = decodeAppleJwsPayload(signedTransactionInfo);
    const transactionId = hinted.transactionId;
    if (!transactionId) return res.json({ok:true,ignored:true});
    const { transaction } = await fetchAppleTransaction(String(transactionId));
    await applyAppleTransaction(transaction);
    res.json({ok:true});
  } catch (error) {
    console.error('Apple billing notification failed', error);
    res.status(500).json({ok:false});
  }
});
'''
if "app.post('/api/billing/apple/verify'" not in text:
    anchor = "app.post('/api/auth/register', async (req, res, next) => {\n"
    if anchor not in text:
        raise SystemExit('auth register route anchor not found')
    text = text.replace(anchor, routes + "\n" + anchor, 1)

server.write_text(text)

data = json.loads(package.read_text())
data.setdefault('dependencies', {})['@apple/app-store-server-library'] = '^3.1.0'
package.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

print('Apple billing backend upgrade applied')
