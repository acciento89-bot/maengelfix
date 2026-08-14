from pathlib import Path
import re

root = Path('.')
server_p = root / 'server/index.js'
compose_p = root / 'docker-compose.yml'
env_p = root / '.env.example'

server = server_p.read_text()

pattern = re.compile(
    r"const applePrivateKey = .*?;\nconst appleBillingConfigured = Boolean\(appleIssuerId && appleKeyId && applePrivateKey\);",
    re.S,
)
replacement = r'''const applePrivateKeyBase64 = String(process.env.APPLE_IAP_PRIVATE_KEY_B64 || '').trim();
const applePrivateKey = applePrivateKeyBase64
  ? Buffer.from(applePrivateKeyBase64, 'base64').toString('utf8').trim()
  : String(process.env.APPLE_IAP_PRIVATE_KEY || '')
      .trim()
      .replace(/^['"]|['"]$/g, '')
      .replace(/\\r\\n/g, '\n')
      .replace(/\\n/g, '\n');
let applePrivateKeyValid = false;
if (applePrivateKey) {
  try {
    const parsedAppleKey = crypto.createPrivateKey(applePrivateKey);
    applePrivateKeyValid = parsedAppleKey.asymmetricKeyType === 'ec';
    if (!applePrivateKeyValid) console.error('Apple IAP private key is not an EC key.');
  } catch (error) {
    console.error('Apple IAP private key could not be parsed:', error.message);
  }
}
const appleBillingConfigured = Boolean(appleIssuerId && appleKeyId && applePrivateKey && applePrivateKeyValid);'''

if 'APPLE_IAP_PRIVATE_KEY_B64' not in server:
    server, count = pattern.subn(replacement, server, count=1)
    if count != 1:
        raise SystemExit('Apple private key anchor not found in server/index.js')
    server_p.write_text(server)

compose = compose_p.read_text()
needle = '      APPLE_IAP_PRIVATE_KEY: ${APPLE_IAP_PRIVATE_KEY:-}\n'
if 'APPLE_IAP_PRIVATE_KEY_B64:' not in compose:
    if needle not in compose:
        raise SystemExit('Apple compose anchor not found')
    compose = compose.replace(needle, needle + '      APPLE_IAP_PRIVATE_KEY_B64: ${APPLE_IAP_PRIVATE_KEY_B64:-}\n', 1)
    compose_p.write_text(compose)

if env_p.exists():
    env = env_p.read_text()
    if 'APPLE_IAP_PRIVATE_KEY_B64=' not in env:
        anchor = 'APPLE_IAP_PRIVATE_KEY=' if 'APPLE_IAP_PRIVATE_KEY=' in env else None
        if anchor:
            pos = env.find('\n', env.find(anchor))
            if pos == -1:
                env += '\nAPPLE_IAP_PRIVATE_KEY_B64=\n'
            else:
                env = env[:pos+1] + 'APPLE_IAP_PRIVATE_KEY_B64=\n' + env[pos+1:]
        else:
            env += '\nAPPLE_IAP_PRIVATE_KEY_B64=\n'
        env_p.write_text(env)

print('Apple IAP base64 private key support prepared')
