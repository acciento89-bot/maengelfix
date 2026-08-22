from pathlib import Path

root = Path(__file__).resolve().parents[1]
server = root / 'server' / 'index.js'
text = server.read_text()

if 'V023_GOOGLE_PLAY_BILLING' not in text:
    raise SystemExit('V023 Google Play billing patch must be applied before V024 RTDN')

constants = r'''

// V024_GOOGLE_PLAY_RTDN
const googlePlayRtdnAudience = String(process.env.GOOGLE_PLAY_RTDN_AUDIENCE || '').trim();
const googlePlayRtdnServiceAccountEmail = String(process.env.GOOGLE_PLAY_RTDN_SERVICE_ACCOUNT_EMAIL || '').trim().toLowerCase();
const googlePlayRtdnConfigured = Boolean(googlePlayRtdnAudience && googlePlayRtdnServiceAccountEmail);
let googleOidcJwksCache = { keys: new Map(), expiresAt: 0 };
'''

if 'V024_GOOGLE_PLAY_RTDN' not in text:
    anchor = 'const googlePlayBillingConfigured = Boolean(googlePlayServiceAccount);\n'
    if anchor not in text:
        raise SystemExit('Google Play billing configured anchor not found')
    text = text.replace(anchor, anchor + constants, 1)

# When one owner/admin manages multiple organizations, prefer the organization that is
# already mapped to the Google obfuscated account hash. This keeps RTDN updates scoped.
old_org_query = """     WHERE om.user_id=$1 AND COALESCE(om.active,true)=true AND om.role IN ('owner','admin')
     ORDER BY om.created_at LIMIT 1`,
    [user.id]
"""
new_org_query = """     WHERE om.user_id=$1 AND COALESCE(om.active,true)=true AND om.role IN ('owner','admin')
     ORDER BY CASE WHEN o.subscription_provider='google_play' AND o.subscription_customer_id=$2 THEN 0 ELSE 1 END, om.created_at LIMIT 1`,
    [user.id, accountHash]
"""
if old_org_query in text:
    text = text.replace(old_org_query, new_org_query, 1)

helpers = r'''

function googlePlayDecodeJwtPart(part) {
  try { return JSON.parse(Buffer.from(String(part || ''), 'base64url').toString('utf8')); }
  catch { return null; }
}

async function googleOidcPublicKey(kid) {
  if (!kid) throw new Error('Google OIDC Key-ID fehlt.');
  if (googleOidcJwksCache.expiresAt <= Date.now() || !googleOidcJwksCache.keys.has(kid)) {
    const response = await fetch('https://www.googleapis.com/oauth2/v3/certs', {headers:{accept:'application/json'}});
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !Array.isArray(payload.keys)) throw new Error('Google OIDC-Schlüssel konnten nicht geladen werden.');
    const keys = new Map();
    for (const jwk of payload.keys) {
      if (jwk?.kid && jwk?.kty === 'RSA' && jwk?.alg === 'RS256') keys.set(jwk.kid, jwk);
    }
    const cacheHeader = response.headers.get('cache-control') || '';
    const maxAge = Number(cacheHeader.match(/max-age=(\d+)/i)?.[1] || 3600);
    googleOidcJwksCache = {keys, expiresAt: Date.now() + Math.max(300, maxAge) * 1000};
  }
  const jwk = googleOidcJwksCache.keys.get(kid);
  if (!jwk) throw new Error('Google OIDC Key-ID ist unbekannt.');
  return crypto.createPublicKey({key:jwk,format:'jwk'});
}

async function verifyGooglePlayRtdnOidc(req) {
  if (!googlePlayRtdnConfigured) throw Object.assign(new Error('Google Play RTDN ist serverseitig nicht konfiguriert.'), {statusCode:503});
  const authorization = String(req.headers.authorization || '');
  const match = authorization.match(/^Bearer\s+(.+)$/i);
  if (!match) throw Object.assign(new Error('Google Play RTDN Authorization fehlt.'), {statusCode:401});
  const token = match[1];
  const parts = token.split('.');
  if (parts.length !== 3) throw Object.assign(new Error('Ungültiges Google OIDC-Token.'), {statusCode:401});
  const header = googlePlayDecodeJwtPart(parts[0]);
  const claims = googlePlayDecodeJwtPart(parts[1]);
  if (!header || !claims || header.alg !== 'RS256') throw Object.assign(new Error('Ungültiger Google OIDC-Header.'), {statusCode:401});

  const publicKey = await googleOidcPublicKey(header.kid);
  const verified = crypto.verify(
    'RSA-SHA256',
    Buffer.from(`${parts[0]}.${parts[1]}`),
    publicKey,
    Buffer.from(parts[2], 'base64url')
  );
  if (!verified) throw Object.assign(new Error('Google OIDC-Signatur ist ungültig.'), {statusCode:401});

  const now = Math.floor(Date.now() / 1000);
  const issuer = String(claims.iss || '');
  const audienceOk = Array.isArray(claims.aud)
    ? claims.aud.includes(googlePlayRtdnAudience)
    : String(claims.aud || '') === googlePlayRtdnAudience;
  const email = String(claims.email || '').toLowerCase();
  const emailVerified = claims.email_verified === true || claims.email_verified === 'true';
  if (!['https://accounts.google.com','accounts.google.com'].includes(issuer)) throw Object.assign(new Error('Google OIDC-Issuer ist ungültig.'), {statusCode:401});
  if (!audienceOk) throw Object.assign(new Error('Google OIDC-Audience ist ungültig.'), {statusCode:401});
  if (!emailVerified || email !== googlePlayRtdnServiceAccountEmail) throw Object.assign(new Error('Google OIDC-Servicekonto ist nicht freigegeben.'), {statusCode:403});
  if (!Number(claims.exp) || Number(claims.exp) <= now - 30) throw Object.assign(new Error('Google OIDC-Token ist abgelaufen.'), {statusCode:401});
  if (Number(claims.iat || 0) > now + 120) throw Object.assign(new Error('Google OIDC-Token liegt unzulässig in der Zukunft.'), {statusCode:401});
  return claims;
}

function decodeGooglePlayRtdnMessage(body) {
  const encoded = body?.message?.data;
  if (!encoded || typeof encoded !== 'string') throw Object.assign(new Error('Google Play RTDN message.data fehlt.'), {statusCode:400});
  try { return JSON.parse(Buffer.from(encoded, 'base64').toString('utf8')); }
  catch { throw Object.assign(new Error('Google Play RTDN message.data ist ungültig.'), {statusCode:400}); }
}

async function googlePlayMappedUserForSubscription(subscription, current) {
  const accountHash = String(subscription?.externalAccountIdentifiers?.obfuscatedExternalAccountId || '').toLowerCase();
  if (!accountHash || !current?.product) return null;
  if (current.product.scope === 'private') {
    const result = await pool.query(
      `SELECT id FROM users WHERE subscription_provider='google_play' AND lower(subscription_customer_id)=lower($1) LIMIT 1`,
      [accountHash]
    );
    return result.rows[0]?.id || null;
  }
  const result = await pool.query(
    `SELECT om.user_id
     FROM organizations o
     JOIN organization_memberships om ON om.organization_id=o.id
     WHERE o.subscription_provider='google_play'
       AND lower(o.subscription_customer_id)=lower($1)
       AND COALESCE(om.active,true)=true
       AND om.role IN ('owner','admin')
     ORDER BY CASE WHEN om.role='owner' THEN 0 ELSE 1 END, om.created_at
     LIMIT 1`,
    [accountHash]
  );
  return result.rows[0]?.user_id || null;
}
'''

if 'function googlePlayDecodeJwtPart' not in text:
    anchor = 'function id() {\n'
    if anchor not in text:
        raise SystemExit('id helper anchor not found')
    text = text.replace(anchor, helpers + '\n' + anchor, 1)

routes = r'''

app.post('/api/billing/google-play/rtdn', async (req, res, next) => {
  try {
    await verifyGooglePlayRtdnOidc(req);
    const notification = decodeGooglePlayRtdnMessage(req.body);
    if (String(notification.packageName || '') !== googlePlayPackageName) {
      return res.status(400).json({error:'Google Play RTDN Paketname stimmt nicht.'});
    }

    // Google sends test notifications without a real purchase token.
    if (notification.testNotification) return res.status(204).end();
    const subscriptionNotification = notification.subscriptionNotification;
    if (!subscriptionNotification?.purchaseToken) {
      // MängelFix currently has subscriptions only; unrelated Play RTDN types are acknowledged.
      return res.status(204).end();
    }

    const purchaseToken = String(subscriptionNotification.purchaseToken);
    const subscription = await fetchGooglePlaySubscription(purchaseToken);
    const current = googlePlayCurrentLineItem(subscription);
    if (!current) {
      console.warn('Google Play RTDN ignored unknown MängelFix product.');
      return res.status(204).end();
    }

    const userId = await googlePlayMappedUserForSubscription(subscription, current);
    if (!userId) {
      // A PURCHASED RTDN can race the app's initial verify call. The app verify stores the
      // account-hash mapping, so acknowledging this race here is safe; later lifecycle RTDNs resolve normally.
      console.info('Google Play RTDN arrived before account mapping; current state will be applied by app verification.');
      return res.status(204).end();
    }

    await applyGooglePlaySubscription(subscription, purchaseToken, userId);
    return res.status(204).end();
  } catch (error) {
    if (error?.statusCode) return res.status(error.statusCode).json({error:error.message});
    next(error);
  }
});
'''

if "app.post('/api/billing/google-play/rtdn'" not in text:
    anchor = "app.post('/api/auth/register', async (req, res, next) => {\n"
    if anchor not in text:
        raise SystemExit('auth register route anchor not found')
    text = text.replace(anchor, routes + '\n' + anchor, 1)

server.write_text(text)
print('Google Play RTDN lifecycle upgrade applied')
