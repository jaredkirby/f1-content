import assert from 'node:assert/strict';
import {test} from 'node:test';
import {sealKey,openKey,matchesOperatorToken} from '../lib/credential-box.ts';
import {readBoundedBody} from '../lib/bounded-body.ts';
const secret=Buffer.alloc(32,7).toString('base64'); // Synthetic encryption fixture.
const context={operationId:'synthetic-operation',userId:'synthetic-user',requestId:'synthetic-request'};
const key='synthetic-provider-key';

test('encrypted handoff round-trips without storing plaintext',async()=>{
  const box=await sealKey(key,secret,context);
  assert.ok(!JSON.stringify(box).includes(key));
  assert.equal(await openKey(box.ciphertext,box.iv,secret,context,200,100),key);
  const another=await sealKey(key,secret,context);
  assert.notEqual(another.iv,box.iv);
});
test('tampering, expiry and other user/operation contexts cannot open a handoff',async()=>{
  const box=await sealKey(key,secret,context);
  await assert.rejects(openKey(box.ciphertext,box.iv,secret,context,100,100));
  await assert.rejects(openKey(box.ciphertext,box.iv,secret,{...context,userId:'different'},200,100));
  await assert.rejects(openKey(box.ciphertext,box.iv,secret,{...context,operationId:'different'},200,100));
  const bytes=Buffer.from(box.ciphertext,'base64');bytes[0]^=1;
  await assert.rejects(openKey(bytes.toString('base64'),box.iv,secret,context,200,100));
});
test('invalid credentials and operator tokens fail without secret diagnostics',async()=>{
  await assert.rejects(sealKey('private invalid key',secret,context),error=>!error.message.includes('private'));
  const token='a'.repeat(64);
  assert.equal(matchesOperatorToken(token,token),true);
  for(const value of [null,'','b'.repeat(64),' '+token])assert.equal(matchesOperatorToken(value,token),false);
});
test('body reader enforces bytes across chunks before unbounded allocation',async()=>{
  assert.equal(await readBoundedBody(new Request('https://example.invalid',{method:'POST',body:'hello'}),5),'hello');
  await assert.rejects(readBoundedBody(new Request('https://example.invalid',{method:'POST',body:'too long'}),4));
});
