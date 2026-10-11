// Integration checks against the supported local sign-in simulation only.
// This script intentionally refuses hosted origins and never records human quality.
import assert from 'node:assert/strict';
import fs from 'node:fs';

const base = new URL(process.argv[2] || 'http://127.0.0.1:5173');
assert.equal(base.protocol, 'http:');
assert.equal(base.hostname, '127.0.0.1');
const pilot = JSON.parse(fs.readFileSync(new URL('../app/data/pilot.json', import.meta.url), 'utf8'));
const anonymous = await fetch(new URL('/api/feedback', base), {redirect:'manual'});
assert.equal(anonymous.status, 401, 'anonymous read must reject');
const signIn = await fetch(new URL('/signin-with-chatgpt?return_to=/', base), {redirect:'manual'});
assert.equal(signIn.status, 302);
const cookie = signIn.headers.get('set-cookie')?.split(';')[0];
assert.ok(cookie, 'supported local sign-in must issue its cookie');
const headers = {'Content-Type':'application/json', Cookie:cookie, Origin:base.origin};
const send = async (body, extra = {}) => fetch(new URL('/api/feedback', base), {
  method:'POST', headers:{...headers,...extra}, body:JSON.stringify(body), redirect:'manual',
});
const note = {requestId:crypto.randomUUID(),kind:'annotation',outcome:null,
  comment:'LOCAL API QA ONLY — idempotency and validation.',timeSec:12,
  manifestSha256:pilot.manifestSha256,videoSha256:pilot.videoSha256};
assert.equal((await fetch(new URL('/api/feedback',base),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(note),redirect:'manual'})).status,401);
const first = await send(note); assert.equal(first.status,201);
const saved = await first.json();
const retry = await send(note); assert.equal(retry.status,200);
assert.equal((await retry.json()).item.id,saved.item.id,'retry must keep the original row');
assert.equal((await send({...note,comment:'Changed payload'})).status,409);
assert.equal((await send({...note,requestId:crypto.randomUUID(),manifestSha256:'stale'})).status,409);
assert.equal((await send({...note,requestId:crypto.randomUUID(),timeSec:pilot.duration+1})).status,400);
assert.equal((await send({...note,requestId:crypto.randomUUID(),userId:'forged'})).status,400);
assert.equal((await send({...note,requestId:crypto.randomUUID()},{Origin:'https://another.example'})).status,403);
const list = await fetch(new URL('/api/feedback',base),{headers:{Cookie:cookie},redirect:'manual'});
assert.equal(list.status,200);
const records = await list.json();
assert.equal(records.items.filter(row=>row.id===saved.item.id).length,1);
assert.equal(saved.item.manifestSha256,pilot.manifestSha256);
assert.equal(saved.item.videoSha256,pilot.videoSha256);
console.log('Passed: authenticated persistence, retry idempotency, immutable payload, stale version, bounded timestamp, protected identity and same-origin checks. Local synthetic feedback only.');
