// Real local HTTP + encrypted D1 handoff. Refuses hosted origins; never calls a model.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {spawnSync} from 'node:child_process';
const base=new URL(process.argv[2]||'http://127.0.0.1:5173');
assert.equal(base.protocol,'http:');assert.equal(base.hostname,'127.0.0.1');
const operation=JSON.parse(fs.readFileSync(new URL('../app/data/credential-operation.json',import.meta.url),'utf8'));
const signIn=await fetch(new URL('/signin-with-chatgpt?return_to=/connect',base),{redirect:'manual'});
const cookie=signIn.headers.get('set-cookie')?.split(';')[0];assert.ok(cookie);
const headers={'Content-Type':'application/json',Cookie:cookie,Origin:base.origin};
const send=body=>fetch(new URL('/api/credential',base),{method:'POST',headers,body:JSON.stringify({persistKeychain:operation.persistKeychain,...body}),redirect:'manual'});
assert.equal((await fetch(new URL('/api/credential',base),{redirect:'manual'})).status,401);
assert.equal((await fetch(new URL('/api/operator/credential',base),{method:'POST',redirect:'manual'})).status,401);
assert.equal((await send({operationId:'stale',requestId:crypto.randomUUID(),key:'synthetic-mobile-key'})).status,409);
assert.equal((await send({operationId:operation.id,requestId:crypto.randomUUID(),key:'invalid key'})).status,400);
assert.equal((await send({operationId:operation.id,requestId:crypto.randomUUID(),key:'x'.repeat(5000)})).status,413);
assert.equal((await send({operationId:operation.id,persistKeychain:!operation.persistKeychain,requestId:crypto.randomUUID(),key:'synthetic-mobile-key'})).status,409);
const body={operationId:operation.id,requestId:crypto.randomUUID(),key:'synthetic-mobile-key'};
const first=await send(body);assert.equal(first.status,201);const record=await first.json();
assert.ok(!JSON.stringify(record).includes(body.key));
const retry=await send(body);assert.equal(retry.status,200);assert.equal((await retry.json()).item.id,record.item.id);
assert.equal((await send({...body,key:'different-synthetic-key'})).status,409);
const script=process.argv[3];assert.ok(script,'Provide the shared one-shot pickup helper path.');
const pickup=spawnSync(process.execPath,[script],{encoding:'utf8',input:JSON.stringify({mode:'verify-local',
  siteUrl:base.origin,operatorToken:'a'.repeat(64),operationId:operation.id,
  persistKeychain:operation.persistKeychain,budgetUsd:operation.budgetUsd,requestSha256:operation.requestSha256})+'\n'});
assert.equal(pickup.status,0,'Shared pickup failed without provider inference.');
assert.ok(pickup.stdout.includes('verified_local_handoff'));assert.ok(!pickup.stdout.includes(body.key));
const consumed=await fetch(new URL('/api/credential',base),{headers:{Cookie:cookie},redirect:'manual'});
assert.equal((await consumed.json()).item.status,'consumed');
const again=await fetch(new URL('/api/operator/credential',base),{method:'POST',
  headers:{Authorization:'Bearer '+'a'.repeat(64)},redirect:'manual'});
assert.equal(again.status,202);
console.log('Passed: authenticated mobile handoff, bounded input, stale operation, idempotency, secret-free acknowledgement, one-time shared pickup and clearing. Local synthetic key only; no provider calls.');
