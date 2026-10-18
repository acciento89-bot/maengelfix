// Isolated PostgreSQL checks only: synthetic receipts, no Google calls or checkout.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import fs from 'node:fs';
import crypto from 'node:crypto';
import pg from 'pg';
import {createReceiptCipher,redactGoogleReceipt,nextReceiptSyncSeconds} from './google-play-receipts.js';

test('Google entitlements reject stale admin refreshes and commit encrypted receipts atomically', {skip:!process.env.MAENGELFIX_ISOLATED_POSTGRES}, async()=>{
 const url=new URL(process.env.MAENGELFIX_ISOLATED_POSTGRES);
 assert.ok(['localhost','127.0.0.1','[::1]'].includes(url.hostname),'Only an isolated local database is allowed');
 const schema='billing_check_'+crypto.randomBytes(8).toString('hex');
 const admin=new pg.Pool({connectionString:url.href});
 await admin.query(`CREATE SCHEMA ${schema}`);
 const pool=new pg.Pool({connectionString:url.href,options:`-c search_path=${schema}`});
 try {
 await pool.query(`CREATE TABLE users(id text PRIMARY KEY,name text,email text,street text,postal_code text,city text,country text,phone text,email_verified_at timestamptz,plan_code text,subscription_status text,subscription_provider text,subscription_customer_id text,subscription_id text,subscription_current_period_end timestamptz,onboarding_completed_at timestamptz,onboarding_use_case text);
 CREATE TABLE organizations(id text PRIMARY KEY,plan_code text,subscription_status text,subscription_provider text,subscription_customer_id text,subscription_id text,subscription_current_period_end timestamptz,trial_ends_at timestamptz,max_members int,max_properties int,max_units int,updated_at timestamptz);
 CREATE TABLE organization_memberships(user_id text,organization_id text,role text,active boolean,created_at timestamptz DEFAULT now());
 CREATE TABLE billing_events(id text PRIMARY KEY,provider text,provider_event_id text UNIQUE,user_id text,organization_id text,event_type text,payload jsonb);
 CREATE TABLE google_play_subscription_receipts(token_hash text PRIMARY KEY,user_id text,encrypted_token text,next_sync_at timestamptz);
 INSERT INTO users(id) VALUES('admin-a'),('admin-b'),('private-a');
 INSERT INTO organizations(id,subscription_provider,subscription_id) VALUES('org','google_play','initial');
 INSERT INTO organization_memberships(user_id,organization_id,role,active) VALUES('admin-a','org','owner',true),('admin-b','org','admin',true);`);
 const source=fs.readFileSync(new URL('./index.js',import.meta.url),'utf8');
 const actual=source.slice(source.indexOf('function googlePlayCurrentLineItem('),source.indexOf('\nfunction id()'));
 const hash=x=>crypto.createHash('sha256').update(x).digest('hex');
 const cipher=createReceiptCipher(crypto.randomBytes(32));
 const products=new Map([['organization',{scope:'organization',planCode:'management_business'}],['private',{scope:'private'}]]);
 const apply=Function('pool','googleReceiptCipher','googlePlayProducts','googlePlayAccountHash','googlePlayTokenHash','nextReceiptSyncSeconds','redactGoogleReceipt','publicUser','hasPrivatePro','billingState','applyPlanLimits','id',actual+'\nreturn applyGooglePlaySubscription;')(pool,cipher,products,hash,hash,nextReceiptSyncSeconds,redactGoogleReceipt,x=>x,()=>false,()=>({active:false}),()=>({maxMembers:10,maxProperties:300,maxUnits:300}),()=>crypto.randomUUID());
 const sub=(user,product='organization')=>({externalAccountIdentifiers:{obfuscatedExternalAccountId:hash(user)},subscriptionState:'SUBSCRIPTION_STATE_ACTIVE',lineItems:[{productId:product,expiryTime:new Date(Date.now()+86400000).toISOString()}]});
 await apply(sub('admin-a'),'old-token','admin-a');
 // Admin B holds the org row while A starts a refresh of its old receipt.
 const blocker=await pool.connect();await blocker.query('BEGIN');
 await blocker.query("UPDATE organizations SET subscription_id=$1,subscription_customer_id=$2 WHERE id='org'",[hash('new-token'),hash('admin-b')]);
 const stale=apply(sub('admin-a'),'old-token','admin-a',true);
 const deadline=Date.now()+5000;let waiting=false;
 while(Date.now()<deadline){
  const q=await admin.query("SELECT 1 FROM pg_stat_activity WHERE query LIKE '%LIMIT 1 FOR UPDATE OF o%' AND wait_event_type='Lock'");
  if(q.rowCount){waiting=true;break;}await new Promise(r=>setTimeout(r,20));
 }
 assert.ok(waiting,'The stale worker must wait on the actual organization row');
 await blocker.query('COMMIT');blocker.release();
 assert.equal(await stale,null);
 assert.equal((await pool.query("SELECT subscription_id FROM organizations WHERE id='org'")).rows[0].subscription_id,hash('new-token'));
 assert.equal((await pool.query('SELECT count(*)::int n FROM billing_events')).rows[0].n,1);
 // A receipt owned by somebody else forces the whole entitlement transaction back.
 await pool.query('INSERT INTO google_play_subscription_receipts VALUES($1,$2,$3,now())',[hash('collision'),'other-user','unreadable']);
 await assert.rejects(apply(sub('private-a','private'),'collision','private-a'),/anderen Konto/);
 assert.equal((await pool.query("SELECT subscription_id FROM users WHERE id='private-a'")).rows[0].subscription_id,null);
 await apply(sub('private-a','private'),'private-token','private-a');
 const record=(await pool.query('SELECT * FROM google_play_subscription_receipts WHERE token_hash=$1',[hash('private-token')])).rows[0];
 assert.equal(cipher.open(record.encrypted_token,record.token_hash,'private-a'),'private-token');
 assert.equal(record.encrypted_token.includes('private-token'),false);
 await pool.query("UPDATE users SET subscription_id='newer' WHERE id='private-a'");
 assert.equal(await apply(sub('private-a','private'),'private-token','private-a',true),null);
 assert.equal((await pool.query("SELECT subscription_id FROM users WHERE id='private-a'")).rows[0].subscription_id,'newer');
 } finally {await pool.end();await admin.query(`DROP SCHEMA ${schema} CASCADE`);await admin.end();}
});
