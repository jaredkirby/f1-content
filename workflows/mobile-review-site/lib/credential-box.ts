// A temporary encrypted handoff. Never include plaintext keys in diagnostics.
export const HANDOFF_TTL_MS = 30 * 60 * 1000;
export type BoxContext = { operationId: string; userId: string; requestId: string };
const encode = (bytes: Uint8Array) => btoa(String.fromCharCode(...bytes));
const decode = (text: string) => Uint8Array.from(atob(text), (char) => char.charCodeAt(0));
const aad = (context: BoxContext) => new TextEncoder().encode(JSON.stringify(context));
async function encryptionKey(secret: string) {
  const bytes = decode(secret);
  if (bytes.length !== 32) throw new Error("Credential handoff is unavailable.");
  return crypto.subtle.importKey("raw", bytes, "AES-GCM", false, ["encrypt", "decrypt"]);
}
export async function sealKey(key: string, secret: string, context: BoxContext) {
  if (!key || key.length > 512 || !/^[!-~]+$/.test(key)) throw new Error("Invalid key format.");
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const encrypted = await crypto.subtle.encrypt({ name: "AES-GCM", iv, additionalData: aad(context) },
    await encryptionKey(secret), new TextEncoder().encode(key));
  return { ciphertext: encode(new Uint8Array(encrypted)), iv: encode(iv) };
}
export async function openKey(ciphertext: string, iv: string, secret: string,
  context: BoxContext, expiresAt: number, now = Date.now()) {
  if (!Number.isSafeInteger(expiresAt) || !Number.isSafeInteger(now) || now >= expiresAt)
    throw new Error("Credential handoff expired.");
  const decrypted = await crypto.subtle.decrypt({ name: "AES-GCM", iv: decode(iv), additionalData: aad(context) },
    await encryptionKey(secret), decode(ciphertext));
  return new TextDecoder("utf-8", { fatal: true }).decode(decrypted);
}
export function matchesOperatorToken(value: string | null, expected: string) {
  if (!value || expected.length < 32 || value.length !== expected.length) return false;
  let difference = 0;
  for (let index = 0; index < expected.length; index++) difference |= value.charCodeAt(index) ^ expected.charCodeAt(index);
  return difference === 0;
}
