import assert from 'node:assert/strict';
import {test} from 'node:test';
import crypto from 'node:crypto';
import {createReceiptCipher,redactGoogleReceipt,runReceiptSync,nextReceiptSyncSeconds} from './google-play-receipts.js';

test('subscription receipts are encrypted and bound to their account and token hash',()=>{
 const cipher=createReceiptCipher(crypto.randomBytes(32));const token='isolated-fake-purchase-token';
 const sealed=cipher.seal(token,'user-a');assert.ok(!sealed.encrypted.includes(token));
 assert.equal(cipher.open(sealed.encrypted,sealed.tokenHash,'user-a'),token);
 assert.throws(()=>cipher.open(sealed.encrypted,sealed.tokenHash,'user-b'));
 assert.throws(()=>cipher.open(sealed.encrypted,'wrong-token-hash','user-a'));
 assert.throws(()=>createReceiptCipher(crypto.randomBytes(32)).open(sealed.encrypted,sealed.tokenHash,'user-a'));
 const data=JSON.parse(sealed.encrypted);data.tag=crypto.randomBytes(16).toString('base64');
 assert.throws(()=>cipher.open(JSON.stringify(data),sealed.tokenHash,'user-a'));
});
test('missing encryption configuration fails closed',()=>{
 const c=createReceiptCipher(null);assert.equal(c.configured,false);assert.throws(()=>c.seal('token','user-a'));
 assert.equal(createReceiptCipher(Buffer.alloc(31)).configured,false);
});
test('Google billing event metadata does not persist linked purchase tokens',()=>{
 const clean=redactGoogleReceipt({linkedPurchaseToken:'raw-secret',lineItems:[{productId:'maengelfix.private.monthly',expiryTime:'2026-11-18T00:00:00Z'}],nested:{purchaseToken:'raw-nested',state:'ACTIVE'}});
 assert.equal(JSON.stringify(clean).includes('raw-'),false);assert.equal(clean.lineItems[0].productId,'maengelfix.private.monthly');assert.equal(clean.nested.state,'ACTIVE');
});
test('renewal sync refreshes verified receipts, isolates failures and never outputs a token',async()=>{
 const cipher=createReceiptCipher(crypto.randomBytes(32));
 const records=['good','transient','wrong-account'].map((t,i)=>({...cipher.seal(t,'u'+i),userId:'u'+i}));
 const applied=[],finished=[],failures=[];
 await runReceiptSync({cipher,records,fetchSubscription:async token=>{if(token==='transient')throw Error('upstream '+token);return {token};},applySubscription:async(s,t,u)=>{if(t==='wrong-account')throw Error('binding mismatch');applied.push([t,u]);},complete:async(r,ok)=>finished.push([r.tokenHash,ok]),onFailure:()=>failures.push('sanitized')});
 assert.deepEqual(applied,[['good','u0']]);assert.deepEqual(finished.map(x=>x[1]),[true,false,false]);assert.equal(failures.length,2);
});

test('renewal boundary is retried promptly rather than deferring a paid renewal for a day',()=>{
 const now=Date.parse('2026-10-18T20:00:00Z');
 assert.equal(nextReceiptSyncSeconds({subscriptionState:'SUBSCRIPTION_STATE_ACTIVE'},{expiryMs:now+86400000},true,now),900);
 assert.equal(nextReceiptSyncSeconds({subscriptionState:'SUBSCRIPTION_STATE_ACTIVE'},{expiryMs:now+10000},true,now),15);
 assert.equal(nextReceiptSyncSeconds({subscriptionState:'SUBSCRIPTION_STATE_ACTIVE'},{expiryMs:now-10000},true,now),15);
 assert.equal(nextReceiptSyncSeconds({subscriptionState:'SUBSCRIPTION_STATE_EXPIRED'},{expiryMs:now-10000},true,now),86400);
 assert.equal(nextReceiptSyncSeconds(null,null,false,now),900);
});

test('canceled and recoverable subscriptions stay fresh even after their old expiry',()=>{
 const now=Date.parse('2026-10-18T20:00:00Z');
 for(const state of ['CANCELED','ON_HOLD','PAUSED','ACTIVE','IN_GRACE_PERIOD']) {
  assert.equal(nextReceiptSyncSeconds({subscriptionState:'SUBSCRIPTION_STATE_'+state},{expiryMs:now-7200000},true,now),900);
 }
 assert.equal(nextReceiptSyncSeconds({subscriptionState:'SUBSCRIPTION_STATE_CANCELED'},{expiryMs:now+10000},true,now),15);
});
