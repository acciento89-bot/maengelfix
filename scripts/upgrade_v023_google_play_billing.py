from pathlib import Path

root = Path(__file__).resolve().parents[1]
server = root / 'server' / 'index.js'
text = server.read_text()

constants = r'''

// V023_GOOGLE_PLAY_BILLING
const googlePlayPackageName = process.env.GOOGLE_PLAY_PACKAGE_NAME || 'com.kamilunavo.maengelfix';
const googlePlayServiceAccountJsonB64 = String(process.env.GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_B64 || '').trim();
let googlePlayServiceAccount = null;
if (googlePlayServiceAccountJsonB64) {
  try {
    googlePlayServiceAccount = JSON.parse(Buffer.from(googlePlayServiceAccountJsonB64, 'base64').toString('utf8'));
    if (!googlePlayServiceAccount?.client_email || !googlePlayServiceAccount?.private_key) {
      throw new Error('client_email/private_key missing');
    }
    const parsedGoogleKey = crypto.createPrivateKey(googlePlayServiceAccount.private_key);
    if (parsedGoogleKey.asymmetricKeyType !== 'rsa') throw new Error('private key is not RSA');
  } catch (error) {
    console.error('Google Play service account could not be parsed:', error.message);
    googlePlayServiceAccount = null;
  }
}
const googlePlayBillingConfigured = Boolean(googlePlayServiceAccount);
const googlePlayProducts = new Map([
  ['com.kamilunavo.maengelfix.privatepro.monthly', {scope:'private',planCode:'private_pro'}],
  ['com.kamilunavo.maengelfix.privatepro.yearly', {scope:'private',planCode:'private_pro'}],
  ['com.kamilunavo.maengelfix.managementstarter.monthly', {scope:'organization',planCode:'management_starter'}],
  ['com.kamilunavo.maengelfix.managementstarter.yearly', {scope:'organization',planCode:'management_starter'}],
  ['com.kamilunavo.maengelfix.managementpro.monthly', {scope:'organization',planCode:'management_pro'}],
  ['com.kamilunavo.maengelfix.managementpro.yearly', {scope:'organization',planCode:'management_pro'}],
  ['com.kamilunavo.maengelfix.managementbusiness.monthly', {scope:'organization',planCode:'management_business'}],
  ['com.kamilunavo.maengelfix.managementbusiness.yearly', {scope:'organization',planCode:'management_business'}]
]);
let googlePlayTokenCache = { accessToken: '', expiresAt: 0 };
'''

if 'V023_GOOGLE_PLAY_BILLING' not in text:
    anchor = 'const appleProductIds = new Set(appleProducts.keys());\n'
    if anchor not in text:
        raise SystemExit('apple product anchor not found')
    text = text.replace(anchor, anchor + constants, 1)

helpers = r'''

function googlePlayAccountHash(userId) {
  return crypto.createHash('sha256').update(String(userId || '').toLowerCase()).digest('hex');
}

function googlePlayTokenHash(token) {
  return crypto.createHash('sha256').update(String(token || '')).digest('hex');
}

function googlePlayJwtPart(value) {
  return Buffer.from(JSON.stringify(value)).toString('base64url');
}

async function googlePlayAccessToken() {
  if (!googlePlayBillingConfigured) throw new Error('Google Play Billing ist serverseitig noch nicht konfiguriert.');
  if (googlePlayTokenCache.accessToken && googlePlayTokenCache.expiresAt > Date.now() + 60_000) {
    return googlePlayTokenCache.accessToken;
  }

  const now = Math.floor(Date.now() / 1000);
  const tokenUri = googlePlayServiceAccount.token_uri || 'https://oauth2.googleapis.com/token';
  const header = googlePlayJwtPart({alg:'RS256',typ:'JWT'});
  const claims = googlePlayJwtPart({
    iss: googlePlayServiceAccount.client_email,
    scope: 'https://www.googleapis.com/auth/androidpublisher',
    aud: tokenUri,
    iat: now,
    exp: now + 3600
  });
  const signingInput = `${header}.${claims}`;
  const signature = crypto.sign('RSA-SHA256', Buffer.from(signingInput), googlePlayServiceAccount.private_key).toString('base64url');
  const assertion = `${signingInput}.${signature}`;

  const response = await fetch(tokenUri, {
    method: 'POST',
    headers: {'content-type':'application/x-www-form-urlencoded'},
    body: new URLSearchParams({
      grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer',
      assertion
    })
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || !payload.access_token) {
    throw new Error(`Google OAuth fehlgeschlagen (${response.status}).`);
  }
  googlePlayTokenCache = {
    accessToken: payload.access_token,
    expiresAt: Date.now() + Math.max(60, Number(payload.expires_in || 3600)) * 1000
  };
  return payload.access_token;
}

async function fetchGooglePlaySubscription(purchaseToken) {
  const accessToken = await googlePlayAccessToken();
  const url = `https://androidpublisher.googleapis.com/androidpublisher/v3/applications/${encodeURIComponent(googlePlayPackageName)}/purchases/subscriptionsv2/tokens/${encodeURIComponent(purchaseToken)}`;
  const response = await fetch(url, {
    headers: {authorization: `Bearer ${accessToken}`, accept: 'application/json'}
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload?.error?.message || `HTTP ${response.status}`;
    throw new Error(`Google Play konnte den Kauf nicht bestätigen: ${detail}`);
  }
  return payload;
}

function googlePlayCurrentLineItem(subscription) {
  const now = Date.now();
  const known = (subscription?.lineItems || [])
    .map(item => ({item, product: googlePlayProducts.get(item?.productId), expiryMs: Date.parse(item?.expiryTime || '') || 0}))
    .filter(entry => entry.product);
  const future = known.filter(entry => entry.expiryMs > now).sort((a,b) => b.expiryMs - a.expiryMs);
  return future[0] || known.sort((a,b) => b.expiryMs - a.expiryMs)[0] || null;
}

function googlePlaySubscriptionActive(subscription, expiryMs) {
  const state = String(subscription?.subscriptionState || '');
  const entitledStates = new Set([
    'SUBSCRIPTION_STATE_ACTIVE',
    'SUBSCRIPTION_STATE_CANCELED',
    'SUBSCRIPTION_STATE_IN_GRACE_PERIOD'
  ]);
  return entitledStates.has(state) && expiryMs > Date.now();
}

async function applyGooglePlaySubscription(subscription, purchaseToken, expectedUserId) {
  const accountHash = String(subscription?.externalAccountIdentifiers?.obfuscatedExternalAccountId || '').toLowerCase();
  const expectedHash = googlePlayAccountHash(expectedUserId);
  if (!accountHash || accountHash !== expectedHash) {
    throw new Error('Google-Play-Kauf gehört nicht zu diesem MängelFix-Konto.');
  }

  const current = googlePlayCurrentLineItem(subscription);
  if (!current) throw new Error('Unbekanntes MängelFix Google-Play-Produkt.');
  const { item, product, expiryMs } = current;
  const active = googlePlaySubscriptionActive(subscription, expiryMs);
  const periodEnd = expiryMs ? new Date(expiryMs) : null;
  const tokenHash = googlePlayTokenHash(purchaseToken);
  const orderId = String(item.latestSuccessfulOrderId || subscription.latestOrderId || tokenHash);
  const eventId = `google_play:${orderId}:${subscription.subscriptionState || 'UNKNOWN'}:${item.expiryTime || ''}`;

  const userResult = await pool.query('SELECT * FROM users WHERE lower(id)=lower($1)', [expectedUserId]);
  const user = userResult.rows[0] || null;
  if (!user) throw new Error('Verknüpftes MängelFix-Konto wurde nicht gefunden.');

  if (product.scope === 'private') {
    // Ein fremdes aktives Store-Abo darf durch Google weder übernommen noch herabgestuft werden.
    if (user.subscription_provider && user.subscription_provider !== 'google_play' && hasPrivatePro(user)) {
      return publicUser(user);
    }
    // Ein alter Google-Status darf keinen inzwischen gewechselten Provider herabstufen.
    if (!active && user.subscription_provider && user.subscription_provider !== 'google_play') {
      return publicUser(user);
    }

    const result = await pool.query(
      `UPDATE users SET
         plan_code=$2,
         subscription_status=$3,
         subscription_provider='google_play',
         subscription_customer_id=$4,
         subscription_id=$5,
         subscription_current_period_end=$6
       WHERE id=$1
       RETURNING id,name,email,street,postal_code,city,country,phone,email_verified_at,plan_code,subscription_status,subscription_current_period_end,onboarding_completed_at,onboarding_use_case`,
      [user.id, active ? 'private_pro' : 'private_free', active ? 'active' : 'inactive', accountHash, tokenHash, periodEnd]
    );

    await pool.query(
      `INSERT INTO billing_events (id,provider,provider_event_id,user_id,event_type,payload)
       VALUES ($1,'google_play',$2,$3,$4,$5::jsonb)
       ON CONFLICT (provider_event_id) DO NOTHING`,
      [id(), eventId, user.id, active ? 'subscription_active' : 'subscription_inactive', JSON.stringify(subscription)]
    );
    return publicUser(result.rows[0]);
  }

  const orgResult = await pool.query(
    `SELECT o.*,om.role
     FROM organization_memberships om
     JOIN organizations o ON o.id=om.organization_id
     WHERE om.user_id=$1 AND COALESCE(om.active,true)=true AND om.role IN ('owner','admin')
     ORDER BY om.created_at LIMIT 1`,
    [user.id]
  );
  const organization = orgResult.rows[0] || null;
  if (!organization) throw new Error('Für dieses MängelFix-Konto wurde keine verwaltbare Hausverwaltung gefunden.');

  if (organization.subscription_provider && organization.subscription_provider !== 'google_play' && billingState(organization).active) {
    return publicUser(user);
  }
  if (!active && organization.subscription_provider && organization.subscription_provider !== 'google_play') {
    return publicUser(user);
  }

  const limits = applyPlanLimits(product.planCode);
  await pool.query(
    `UPDATE organizations SET
       plan_code=CASE WHEN $2::boolean THEN $3 ELSE plan_code END,
       subscription_status=$4,
       subscription_provider='google_play',
       subscription_customer_id=$5,
       subscription_id=$6,
       subscription_current_period_end=$7,
       trial_ends_at=CASE WHEN $2::boolean THEN NULL ELSE trial_ends_at END,
       max_members=CASE WHEN $2::boolean THEN $8 ELSE max_members END,
       max_properties=CASE WHEN $2::boolean THEN $9 ELSE max_properties END,
       max_units=CASE WHEN $2::boolean THEN $10 ELSE max_units END,
       updated_at=now()
     WHERE id=$1`,
    [
      organization.id,
      active,
      product.planCode,
      active ? 'active' : 'inactive',
      accountHash,
      tokenHash,
      periodEnd,
      limits?.maxMembers || organization.max_members,
      limits?.maxProperties || organization.max_properties,
      limits?.maxUnits || organization.max_units
    ]
  );

  await pool.query(
    `INSERT INTO billing_events (id,provider,provider_event_id,organization_id,user_id,event_type,payload)
     VALUES ($1,'google_play',$2,$3,$4,$5,$6::jsonb)
     ON CONFLICT (provider_event_id) DO NOTHING`,
    [id(), eventId, organization.id, user.id, active ? 'subscription_active' : 'subscription_inactive', JSON.stringify(subscription)]
  );
  return publicUser(user);
}
'''

if 'function googlePlayAccountHash' not in text:
    anchor = 'function id() {\n'
    if anchor not in text:
        raise SystemExit('id helper anchor not found')
    text = text.replace(anchor, helpers + '\n' + anchor, 1)

routes = r'''

app.post('/api/billing/google-play/verify', auth, async (req, res, next) => {
  try {
    if (!googlePlayBillingConfigured) {
      return res.status(503).json({error:'Google Play Billing ist serverseitig noch nicht konfiguriert.',code:'GOOGLE_PLAY_NOT_CONFIGURED'});
    }
    const purchaseToken = cleanText(req.body.purchaseToken, 4096);
    const claimedProductId = cleanText(req.body.productId, 200);
    if (!purchaseToken) return res.status(400).json({error:'Google-Play-Purchase-Token fehlt.'});

    const subscription = await fetchGooglePlaySubscription(purchaseToken);
    const current = googlePlayCurrentLineItem(subscription);
    if (!current) return res.status(400).json({error:'Google Play meldet kein bekanntes MängelFix-Abo.'});
    if (claimedProductId && claimedProductId !== current.item.productId) {
      return res.status(400).json({error:'Google-Play-Produkt stimmt nicht mit dem bestätigten Kauf überein.'});
    }

    const user = await applyGooglePlaySubscription(subscription, purchaseToken, req.user.id);
    res.json({
      user,
      productId: current.item.productId,
      subscriptionState: subscription.subscriptionState,
      expiresAt: current.item.expiryTime || null,
      acknowledgementState: subscription.acknowledgementState || null,
      testPurchase: Boolean(subscription.testPurchase)
    });
  } catch (error) { next(error); }
});
'''

if "app.post('/api/billing/google-play/verify'" not in text:
    anchor = "app.post('/api/auth/register', async (req, res, next) => {\n"
    if anchor not in text:
        raise SystemExit('auth register route anchor not found')
    text = text.replace(anchor, routes + '\n' + anchor, 1)

server.write_text(text)
print('Google Play billing backend upgrade applied')
