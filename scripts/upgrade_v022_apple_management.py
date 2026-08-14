from pathlib import Path
import json
import re

root = Path('.')
server_p = root / 'server' / 'index.js'
package_p = root / 'server' / 'package.json'
server = server_p.read_text()
package = json.loads(package_p.read_text())

products_pattern = re.compile(r"const appleProductIds = new Set\(\[.*?\]\);", re.S)
products_replacement = r'''const appleProducts = new Map([
  ['com.kamilunavo.maengelfix.privatepro.monthly', {scope:'private',planCode:'private_pro'}],
  ['com.kamilunavo.maengelfix.privatepro.yearly', {scope:'private',planCode:'private_pro'}],
  ['com.kamilunavo.maengelfix.managementstarter.monthly', {scope:'organization',planCode:'management_starter'}],
  ['com.kamilunavo.maengelfix.managementstarter.yearly', {scope:'organization',planCode:'management_starter'}],
  ['com.kamilunavo.maengelfix.managementpro.monthly', {scope:'organization',planCode:'management_pro'}],
  ['com.kamilunavo.maengelfix.managementpro.yearly', {scope:'organization',planCode:'management_pro'}],
  ['com.kamilunavo.maengelfix.managementbusiness.monthly', {scope:'organization',planCode:'management_business'}],
  ['com.kamilunavo.maengelfix.managementbusiness.yearly', {scope:'organization',planCode:'management_business'}]
]);
const appleProductIds = new Set(appleProducts.keys());'''
server, count = products_pattern.subn(products_replacement, server, count=1)
if count != 1:
    raise SystemExit('Apple product block not found')

apply_pattern = re.compile(r"async function applyAppleTransaction\(transaction, expectedUserId = null\) \{.*?\n\}\n\nfunction id\(\) \{", re.S)
apply_replacement = r'''async function applyAppleTransaction(transaction, expectedUserId = null) {
  if (transaction.bundleId !== appleBundleId) throw new Error('Apple-Transaktion gehört nicht zu MängelFix.');
  const product = appleProducts.get(transaction.productId);
  if (!product) throw new Error('Unbekanntes MängelFix Apple-Produkt.');

  const tokenUserId = String(transaction.appAccountToken || '').toLowerCase();
  const expected = String(expectedUserId || '').toLowerCase();
  const subscriptionId = String(transaction.originalTransactionId || transaction.transactionId || '');
  if (expected && tokenUserId && tokenUserId !== expected) throw new Error('Apple-Transaktion gehört zu einem anderen MängelFix-Konto.');

  const expiresMs = Number(transaction.expiresDate || 0);
  const active = !transaction.revocationDate && expiresMs > Date.now();
  const periodEnd = expiresMs ? new Date(expiresMs) : null;

  let user = null;
  const requestedUserId = tokenUserId || expected;
  if (requestedUserId) {
    const current = await pool.query('SELECT * FROM users WHERE lower(id)=lower($1)', [requestedUserId]);
    user = current.rows[0] || null;
  }
  if (!user && subscriptionId) {
    const current = await pool.query('SELECT * FROM users WHERE subscription_provider=\'apple\' AND subscription_id=$1 LIMIT 1', [subscriptionId]);
    user = current.rows[0] || null;
  }

  if (product.scope === 'private') {
    if (!user) throw new Error('Verknüpftes MängelFix-Konto wurde nicht gefunden.');
    if (expected && String(user.id).toLowerCase() !== expected) throw new Error('Apple-Transaktion gehört zu einem anderen MängelFix-Konto.');

    // Ein bereits aktives Stripe-Abo wird durch Apple-Statusmeldungen nicht überschrieben.
    if (user.subscription_provider === 'stripe' && user.plan_code === 'private_pro' && ['active','trialing'].includes(user.subscription_status)) {
      return publicUser(user);
    }

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
        user.id,
        active ? 'private_pro' : 'private_free',
        active ? 'active' : 'inactive',
        transaction.appAccountToken || user.id,
        subscriptionId,
        periodEnd
      ]
    );

    await pool.query(
      `INSERT INTO billing_events (id,provider,provider_event_id,user_id,event_type,payload)
       VALUES ($1,'apple',$2,$3,$4,$5::jsonb)
       ON CONFLICT (provider_event_id) DO NOTHING`,
      [id(), String(transaction.transactionId), user.id, active ? 'subscription_active' : 'subscription_inactive', JSON.stringify(transaction)]
    );
    return publicUser(result.rows[0]);
  }

  let organization = null;
  if (user) {
    const org = await pool.query(
      `SELECT o.*,om.role
       FROM organization_memberships om
       JOIN organizations o ON o.id=om.organization_id
       WHERE om.user_id=$1 AND COALESCE(om.active,true)=true AND om.role IN ('owner','admin')
       ORDER BY om.created_at LIMIT 1`,
      [user.id]
    );
    organization = org.rows[0] || null;
  }
  if (!organization && subscriptionId) {
    const org = await pool.query(`SELECT o.*,'owner'::text role FROM organizations o WHERE o.subscription_provider='apple' AND o.subscription_id=$1 LIMIT 1`, [subscriptionId]);
    organization = org.rows[0] || null;
  }
  if (!organization) throw new Error('Für dieses MängelFix-Konto wurde keine verwaltbare Hausverwaltung gefunden.');
  if (expected && (!user || String(user.id).toLowerCase() !== expected)) throw new Error('Apple-Transaktion gehört zu einem anderen MängelFix-Konto.');

  // Ein aktiver Stripe-Verwaltungstarif wird nicht durch eine Apple-Statusmeldung überschrieben.
  if (organization.subscription_provider === 'stripe' && billingState(organization).active) {
    if (!user) throw new Error('Verknüpftes MängelFix-Konto wurde nicht gefunden.');
    return publicUser(user);
  }

  const limits = applyPlanLimits(product.planCode);
  await pool.query(
    `UPDATE organizations SET
       plan_code=CASE WHEN $2::boolean THEN $3 ELSE plan_code END,
       subscription_status=$4,
       subscription_provider='apple',
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
      user?.id || transaction.appAccountToken || organization.id,
      subscriptionId,
      periodEnd,
      limits?.maxMembers || organization.max_members,
      limits?.maxProperties || organization.max_properties,
      limits?.maxUnits || organization.max_units
    ]
  );

  await pool.query(
    `INSERT INTO billing_events (id,provider,provider_event_id,organization_id,user_id,event_type,payload)
     VALUES ($1,'apple',$2,$3,$4,$5,$6::jsonb)
     ON CONFLICT (provider_event_id) DO NOTHING`,
    [id(), String(transaction.transactionId), organization.id, user?.id || null, active ? 'subscription_active' : 'subscription_inactive', JSON.stringify(transaction)]
  );

  if (!user) {
    const owner = await pool.query(
      `SELECT u.* FROM organization_memberships om JOIN users u ON u.id=om.user_id
       WHERE om.organization_id=$1 AND om.role='owner' AND COALESCE(om.active,true)=true LIMIT 1`,
      [organization.id]
    );
    user = owner.rows[0] || null;
  }
  if (!user) throw new Error('Verknüpftes MängelFix-Konto wurde nicht gefunden.');
  return publicUser(user);
}

function id() {'''
server, count = apply_pattern.subn(apply_replacement, server, count=1)
if count != 1:
    raise SystemExit('applyAppleTransaction function not found')

old_entitlement = "return {scope:'organization',pro:Boolean(st.active),planCode:org.plan_code,status:org.subscription_status,trialEndsAt:org.trial_ends_at||null,usage:"
new_entitlement = "return {scope:'organization',pro:Boolean(st.active),planCode:org.plan_code,status:org.subscription_status,trialEndsAt:org.trial_ends_at||null,role:org.role||null,provider:org.subscription_provider||null,usage:"
if old_entitlement not in server:
    raise SystemExit('Organization entitlement response not found')
server = server.replace(old_entitlement, new_entitlement, 1)

server = server.replace("version: '0.21.0'", "version: '0.22.0'", 1)
package['version'] = '0.22.0'

server_p.write_text(server)
package_p.write_text(json.dumps(package, ensure_ascii=False, indent=2) + '\n')
print('Apple management subscriptions prepared')
