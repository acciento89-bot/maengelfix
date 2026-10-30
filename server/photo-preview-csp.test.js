import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import http from 'node:http';

// Do not import index.js: its database/authentication startup is unrelated to CSP.
// Exercise the actual installed middleware using the actual source expression.
const here = dirname(fileURLToPath(import.meta.url));
const dependencyDir = process.env.MAENGELFIX_CSP_TEST_DEPENDENCY_DIR || here;
const sourcePath = process.env.MAENGELFIX_CSP_TEST_SOURCE || join(here, 'index.js');
const require = createRequire(join(dependencyDir, 'package.json'));
const express = require('express');
const helmet = require('helmet');
const source = readFileSync(sourcePath, 'utf8');

function extractMountedHelmet(text) {
  const matches = [...text.matchAll(/^app\.use\((helmet\([^\r\n]+\))\);$/gm)];
  assert.equal(matches.length, 1, 'Expected exactly one mounted one-line Helmet configuration');
  const match = matches[0];
  assert.ok(text.indexOf('const app = express();') < match.index);
  assert.ok(match.index < text.indexOf("app.use(express.json("), 'Helmet must precede request routes');
  return match[1];
}
const expression = extractMountedHelmet(source);

async function actualHeaders(code) {
  const middleware = vm.runInNewContext(code, { helmet }, { timeout: 1000 });
  assert.equal(typeof middleware, 'function');
  const app = express();
  app.use(middleware);
  // Neutral local route, not the application, account, database or deployed SPA.
  app.get('/workspace', (_req, res) => res.type('html').send('<!doctype html><title>CSP fixture</title>'));
  const server = app.listen(0, '127.0.0.1');
  try {
    await new Promise((resolve, reject) => {
      if (server.listening) resolve();
      else { server.once('listening', resolve); server.once('error', reject); }
    });
    return await new Promise((resolve, reject) => {
      const request = http.get({ hostname: '127.0.0.1', port: server.address().port, path: '/workspace', agent: false }, response => {
        const headers = Object.fromEntries(Object.entries(response.headers).filter(([name]) => !['date', 'connection', 'keep-alive'].includes(name)));
        response.resume();
        response.once('end', () => { try { assert.equal(response.statusCode, 200); resolve(headers); } catch (error) { reject(error); } });
        response.once('error', reject);
      });
      request.setTimeout(2000, () => request.destroy(new Error('Local CSP fixture timeout')));
      request.once('error', reject);
    });
  } finally {
    await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
  }
}
function directives(value) {
  assert.equal(typeof value, 'string', 'Enforced CSP header is mandatory');
  const result = {};
  for (const part of value.split(';')) {
    const [name, ...values] = part.trim().split(/\s+/);
    if (!name) continue;
    assert.ok(!(name in result), `Duplicate CSP directive ${name}`);
    result[name] = values;
  }
  return result;
}
const baselinePromise = actualHeaders("helmet({ crossOriginResourcePolicy: { policy: 'same-origin' } })");
async function assertPreviewOnlyChange(code) {
  const [baseline, current] = await Promise.all([baselinePromise, actualHeaders(code)]);
  const oldPolicy = directives(baseline['content-security-policy']);
  const newPolicy = directives(current['content-security-policy']);
  assert.deepEqual(newPolicy['img-src'], ["'self'", 'data:', 'blob:']);
  assert.deepEqual(oldPolicy['img-src'], ["'self'", 'data:']);
  delete oldPolicy['img-src'];
  delete newPolicy['img-src'];
  assert.deepEqual(newPolicy, oldPolicy, 'Only img-src may change; all other default directives remain enforced');
  const { ['content-security-policy']: _old, ...oldHeaders } = baseline;
  const { ['content-security-policy']: _new, ...newHeaders } = current;
  assert.deepEqual(newHeaders, oldHeaders, 'All other actual HTTP/security headers remain unchanged');
  assert.equal(current['cross-origin-resource-policy'], 'same-origin');
  assert.equal(current['content-security-policy-report-only'], undefined);
  return current;
}

test('actual mounted server middleware allows local Blob previews and preserves all other HTTP security headers', async () => {
  await assertPreviewOnlyChange(expression);
});
for (const [name, mutate] of [
  ['missing blob image permission', text => text.replace(', "blob:"', '')],
  ['disabled CSP', text => text.replace(/contentSecurityPolicy: \{ directives: \{ imgSrc: \[[^\]]+\] \} \}/, 'contentSecurityPolicy: false')],
  ['disabled defaults', text => text.replace('directives: { imgSrc:', "useDefaults: false, directives: { defaultSrc: [\"'self'\"], imgSrc:")],
  ['inline script relaxation', text => text.replace('directives: { imgSrc:', "directives: { scriptSrc: [\"'self'\", \"'unsafe-inline'\"], imgSrc:")],
  ['connect source expansion', text => text.replace('directives: { imgSrc:', "directives: { connectSrc: [\"'self'\", 'blob:'], imgSrc:")],
  ['wildcard image source', text => text.replace('"blob:"', '"*"')],
  ['disabled same-origin resource policy', text => text.replace("crossOriginResourcePolicy: { policy: 'same-origin' }", 'crossOriginResourcePolicy: false')],
]) {
  test(`negative control rejects ${name}`, async () => {
    const altered = mutate(expression);
    assert.notEqual(altered, expression, 'Negative control must change actual source expression');
    await assert.rejects(() => assertPreviewOnlyChange(altered));
  });
}
test('missing or duplicate actual Helmet mount is rejected', () => {
  assert.throws(() => extractMountedHelmet(source.replace(`app.use(${expression});`, '')));
  assert.throws(() => extractMountedHelmet(source + `\napp.use(${expression});\n`));
});
