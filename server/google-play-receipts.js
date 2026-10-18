import crypto from 'node:crypto';
import fs from 'node:fs';

export function loadReceiptKey(file) {
  try { const key=Buffer.from(fs.readFileSync(file,'utf8').trim(),'base64');return key.length===32?key:null; } catch { return null; }
}
export function createReceiptCipher(key) {
  const configured=Buffer.isBuffer(key)&&key.length===32;
  const hash=token=>crypto.createHash('sha256').update(token).digest('hex');
  return {
    configured,
    seal(token,userId) {
      if(!configured)throw Error('Google receipt encryption is not configured');
      const tokenHash=hash(token),iv=crypto.randomBytes(12),cipher=crypto.createCipheriv('aes-256-gcm',key,iv);
      cipher.setAAD(Buffer.from(JSON.stringify([tokenHash,userId])));
      const data=Buffer.concat([cipher.update(token,'utf8'),cipher.final()]);
      return {tokenHash,encrypted:JSON.stringify({v:1,iv:iv.toString('base64'),tag:cipher.getAuthTag().toString('base64'),data:data.toString('base64')})};
    },
    open(encrypted,tokenHash,userId) {
      if(!configured)throw Error('Google receipt encryption is not configured');
      const x=JSON.parse(encrypted);if(x.v!==1)throw Error('Unsupported receipt envelope');
      const decipher=crypto.createDecipheriv('aes-256-gcm',key,Buffer.from(x.iv,'base64'));
      decipher.setAAD(Buffer.from(JSON.stringify([tokenHash,userId])));decipher.setAuthTag(Buffer.from(x.tag,'base64'));
      const token=Buffer.concat([decipher.update(Buffer.from(x.data,'base64')),decipher.final()]).toString('utf8');
      if(hash(token)!==tokenHash)throw Error('Receipt hash mismatch');return token;
    },
  };
}
export function redactGoogleReceipt(value) {
  if(Array.isArray(value))return value.map(redactGoogleReceipt);
  if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).filter(([k])=>!/token$/i.test(k)).map(([k,v])=>[k,redactGoogleReceipt(v)]));
  return value;
}
export async function runReceiptSync({cipher,records,fetchSubscription,applySubscription,complete,onFailure}) {
  for(const record of records){
    try {
      const token=cipher.open(record.encrypted,record.tokenHash,record.userId);
      const subscription=await fetchSubscription(token);
      await applySubscription(subscription,token,record.userId);
      await complete(record,true,subscription);
    }catch{
      onFailure();await complete(record,false,null);
    }
  }
}

export function nextReceiptSyncSeconds(subscription, current, ok, now=Date.now()) {
  if(!ok)return 900;
  const state=subscription?.subscriptionState;
  const recoverable=['ACTIVE','CANCELED','IN_GRACE_PERIOD','ON_HOLD','PAUSED','PENDING'].some(value=>state==='SUBSCRIPTION_STATE_'+value);
  if(recoverable){
    if(current&&current.expiryMs>now-3600000)return Math.max(15,Math.min(900,Math.floor((current.expiryMs-now-30000)/1000)));
    return 900;
  }
  return 86400;
}
