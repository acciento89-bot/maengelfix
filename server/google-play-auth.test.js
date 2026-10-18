import assert from 'node:assert/strict';
import { test } from 'node:test';
import { generateKeyPairSync } from 'node:crypto';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createGooglePlayAuth } from './google-play-auth.js';

test('missing or malformed credentials never enable paid access', async () => {
  for (const env of [{}, {GOOGLE_APPLICATION_CREDENTIALS:'/missing/runtime.json'}, {GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_B64:'not-json'}]) {
    const auth = createGooglePlayAuth(env);
    assert.equal(auth.configured, false);
    await assert.rejects(auth.accessToken(), /nicht konfiguriert/);
  }
});

test('keyless runtime credentials use only Android Publisher scope and preserve the project', async () => {
  const root = mkdtempSync(join(tmpdir(), 'maengelfix-auth-'));
  try {
    const file = join(root, 'runtime.json');
    writeFileSync(file, JSON.stringify({type:'external_account',audience:'//iam.googleapis.com/projects/1/locations/global/workloadIdentityPools/maengelfix-runtime/providers/prod-x509',subject_token_type:'urn:ietf:params:oauth:token-type:mtls',token_url:'https://sts.mtls.googleapis.com/v1/token',credential_source:{certificate:{certificate_config_location:'/run/secrets/maengelfix/certificate-config.json'}}}));
    let options;
    class FakeGoogleAuth {
      constructor(value) { options = value; }
      async getAccessToken() { return 'isolated-test-token'; }
    }
    const auth = createGooglePlayAuth({GOOGLE_APPLICATION_CREDENTIALS:file,GOOGLE_CLOUD_PROJECT:'owned-project'}, FakeGoogleAuth);
    assert.equal(auth.configured, true);
    assert.equal(await auth.accessToken(), 'isolated-test-token');
    assert.deepEqual(options.scopes, ['https://www.googleapis.com/auth/androidpublisher']);
    assert.equal(options.projectId, 'owned-project');
    assert.equal(options.keyFilename, file);
    assert.equal(options.credentials, undefined);
  } finally { rmSync(root, {recursive:true,force:true}); }
});

test('unsupported JSON cannot silently enable billing', () => {
  const root = mkdtempSync(join(tmpdir(), 'maengelfix-auth-'));
  try {
    const file=join(root,'runtime.json');
    for (const data of [{type:'authorized_user'}, {type:'external_account'}, {type:'service_account',client_email:'missing-key'}]) {
      writeFileSync(file, JSON.stringify(data));
      assert.equal(createGooglePlayAuth({GOOGLE_APPLICATION_CREDENTIALS:file}).configured, false);
    }
  } finally { rmSync(root, {recursive:true,force:true}); }
});

test('OAuth failures and empty responses never return a usable token or leak credentials', async () => {
  const root = mkdtempSync(join(tmpdir(), 'maengelfix-auth-'));
  try {
    const file=join(root,'runtime.json');
    writeFileSync(file, JSON.stringify({type:'external_account',audience:'owned-audience',subject_token_type:'urn:ietf:params:oauth:token-type:mtls',token_url:'https://sts.mtls.googleapis.com/v1/token',credential_source:{certificate:{certificate_config_location:'/private/config'}}}));
    for (const result of [null, '', new Error('sensitive-upstream-response')]) {
      class FakeGoogleAuth { async getAccessToken() { if(result instanceof Error) throw result; return result; } }
      await assert.rejects(createGooglePlayAuth({GOOGLE_APPLICATION_CREDENTIALS:file},FakeGoogleAuth).accessToken(), error => /Google OAuth/.test(error.message) && !error.message.includes('sensitive'));
    }
  } finally { rmSync(root, {recursive:true,force:true}); }
});


test('existing RSA service-account configuration is preserved', async () => {
  const {privateKey} = generateKeyPairSync('rsa', {modulusLength:2048,privateKeyEncoding:{type:'pkcs8',format:'pem'},publicKeyEncoding:{type:'spki',format:'pem'}});
  const credentials={type:'service_account',client_email:'test@owned-project.iam.gserviceaccount.com',private_key:privateKey};
  let options;
  class FakeGoogleAuth { constructor(value) { options=value; } async getAccessToken() { return 'isolated-test-token'; } }
  const auth=createGooglePlayAuth({GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_B64:Buffer.from(JSON.stringify(credentials)).toString('base64')},FakeGoogleAuth);
  assert.equal(auth.configured,true);
  assert.equal(await auth.accessToken(),'isolated-test-token');
  assert.deepEqual(options.credentials,credentials);
  assert.equal(options.keyFilename,undefined);
});
