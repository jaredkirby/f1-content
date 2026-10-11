// Only the deployment's auth, configuration and database boundaries are replaced.
import {DatabaseSync} from 'node:sqlite';
import {drizzle} from 'drizzle-orm/sqlite-proxy';
export const env = {MOBILE_CREDENTIAL_ENCRYPTION_KEY: Buffer.alloc(32,7).toString('base64'),
  MOBILE_CREDENTIAL_OPERATOR_TOKEN: 'a'.repeat(64)};
export const operation = {id:'0123456789abcdef01234567:transient-v1',persistKeychain:false,
  enabled:true,budgetUsd:1,maxCalls:1,requestSha256:'a'.repeat(64)};
export default operation;
export let signedIn = true;
export function setSignedIn(value) { signedIn=value; }
export async function getChatGPTUser() { return signedIn ? {userId:'synthetic-user'} : null; }
const sqlite = new DatabaseSync(':memory:');
sqlite.exec(`CREATE TABLE mobile_credentials (
  id TEXT PRIMARY KEY, operation_id TEXT NOT NULL, user_id TEXT NOT NULL,
  request_id TEXT NOT NULL, ciphertext TEXT, iv TEXT, status TEXT NOT NULL,
  expires_at INTEGER NOT NULL, created_at TEXT NOT NULL, consumed_at TEXT,
  UNIQUE(user_id,request_id));`);
const db=drizzle(async(sql,params,method)=>{
  const statement=sqlite.prepare(sql);
  if(method==='run'){statement.run(...params);return {rows:[]};}
  const rows=statement.all(...params).map(row=>Object.values(row));
  return {rows:method==='get'?rows[0]:rows};
});
export function getDb(){return db;}
