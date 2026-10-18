import crypto from 'node:crypto';
import fs from 'node:fs';
import { GoogleAuth } from 'google-auth-library';

function validCredentials(credentials) {
  if (credentials?.type === 'external_account') {
    return Boolean(credentials.audience && credentials.subject_token_type && credentials.token_url && credentials.credential_source);
  }
  if (credentials?.client_email && credentials?.private_key) {
    return crypto.createPrivateKey(credentials.private_key).asymmetricKeyType === 'rsa';
  }
  return false;
}

// Supports the mounted X509 federation configuration without creating Google keys.
// Existing installations using a legacy base64 service account remain compatible.
export function createGooglePlayAuth(env = process.env, Auth = GoogleAuth) {
  let auth = null;
  try {
    const options = {scopes:['https://www.googleapis.com/auth/androidpublisher']};
    if (env.GOOGLE_CLOUD_PROJECT) options.projectId = env.GOOGLE_CLOUD_PROJECT;
    const file = String(env.GOOGLE_APPLICATION_CREDENTIALS || '').trim();
    const legacy = String(env.GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_B64 || '').trim();
    if (file) {
      const credentials = JSON.parse(fs.readFileSync(file, 'utf8'));
      if (validCredentials(credentials)) options.keyFilename = file;
    } else if (legacy) {
      const credentials = JSON.parse(Buffer.from(legacy, 'base64').toString('utf8'));
      if (validCredentials(credentials)) options.credentials = credentials;
    }
    if (options.keyFilename || options.credentials) auth = new Auth(options);
  } catch {
    // Credential material and upstream authentication responses must not reach logs.
  }
  return {
    configured: Boolean(auth),
    async accessToken() {
      if (!auth) throw new Error('Google Play Billing ist serverseitig noch nicht konfiguriert.');
      try {
        const token = await auth.getAccessToken();
        if (!token || typeof token !== 'string') throw new Error('No access token');
        return token;
      } catch {
        throw new Error('Google OAuth konnte nicht bestätigt werden.');
      }
    },
  };
}
