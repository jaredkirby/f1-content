import assert from 'node:assert/strict';
import {test} from 'node:test';
import {registerHooks,stripTypeScriptTypes,createRequire} from 'node:module';
import fs from 'node:fs';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=new URL('../../f1_pipeline/resources/mobile-review-site/',import.meta.url);
const environment=new URL('./environment.mjs',import.meta.url).href;
const require=createRequire(import.meta.url);
registerHooks({
  resolve(specifier,context,next){
    if(['cloudflare:workers','@/db','@/app/chatgpt-auth','@/app/data/credential-operation.json'].includes(specifier))
      return {url:environment,shortCircuit:true};
    if(specifier.startsWith('@/')){
      const relative=specifier.slice(2);
      return {url:new URL(relative+(relative.endsWith('.mjs')?'':'.ts'),root).href,shortCircuit:true};
    }
    if(specifier==='zod'||specifier.startsWith('drizzle-orm'))
      return next(pathToFileURL(require.resolve(specifier)).href,context);
    return next(specifier,context);
  },
  load(url,context,next){
    if(url.endsWith('.ts')) return {format:'module',source:stripTypeScriptTypes(fs.readFileSync(fileURLToPath(url),'utf8')),shortCircuit:true};
    return next(url,context);
  }
});
const {operation,setSignedIn}=await import('./environment.mjs');
const submit=await import(new URL('app/api/credential/route.ts',root));
const pickup=await import(new URL('app/api/operator/credential/route.ts',root));
const {storageOperationId}=await import(new URL('lib/credential-operation.mjs',root));
const baseId=operation.id.slice(0,24);
const key='synthetic-mobile-key';
const send=body=>submit.POST(new Request('https://example.invalid/api/credential',{
  method:'POST',headers:{origin:'https://example.invalid'},body:JSON.stringify(body)}));
const collect=()=>pickup.POST(new Request('https://example.invalid/api/operator/credential',{
  method:'POST',headers:{authorization:'Bearer '+'a'.repeat(64)}}));

test('HTTP handoff rejects stale pages and pending keys after storage changes in either direction',async()=>{
  for(const before of [false,true]){
    operation.persistKeychain=before;operation.id=storageOperationId(baseId,before);
    const body={operationId:operation.id,persistKeychain:before,requestId:crypto.randomUUID(),key};
    const accepted=await send(body);assert.equal(accepted.status,201);
    assert.ok(!(await accepted.text()).includes(key));
    // A config-only edit must not reinterpret the pending key or a stale page.
    operation.persistKeychain=!before;
    assert.equal((await collect()).status,409);
    assert.equal((await send({...body,requestId:crypto.randomUUID()})).status,409);
    operation.id=storageOperationId(baseId,!before);
    assert.equal((await collect()).status,202);
    assert.equal((await send({...body,requestId:crypto.randomUUID()})).status,409);
    const fresh={...body,operationId:operation.id,persistKeychain:!before,requestId:crypto.randomUUID()};
    assert.equal((await send(fresh)).status,201);
    assert.equal((await send(fresh)).status,200);
    const result=await collect();assert.equal(result.status,200);
    const handoff=await result.json();assert.equal(handoff.key,key);
    assert.equal(handoff.persistKeychain,!before);assert.equal(handoff.operationId,operation.id);
    assert.equal((await collect()).status,202);
    // Collect the original with its original explicit choice; it was never consumed by the change.
    operation.persistKeychain=before;operation.id=body.operationId;
    assert.equal((await collect()).status,200);
  }
});

test('HTTP handoff requires explicit boolean consent and preserves auth boundaries',async()=>{
  const body={operationId:operation.id,requestId:crypto.randomUUID(),key};
  for(const value of [undefined,null,'false',0])
    assert.equal((await send({...body,persistKeychain:value})).status,400);
  assert.equal((await send({...body,persistKeychain:!operation.persistKeychain})).status,409);
  setSignedIn(false);
  assert.equal((await send({...body,persistKeychain:operation.persistKeychain})).status,401);
  setSignedIn(true);
  assert.equal((await pickup.POST(new Request('https://example.invalid',{method:'POST'}))).status,401);
});
