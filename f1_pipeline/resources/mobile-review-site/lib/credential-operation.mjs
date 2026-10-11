// Storage choice is immutable within an operation. Old unbound IDs fail closed.
export function storageOperationId(baseId, persistKeychain) {
  if (!/^[a-f0-9]{24}$/.test(baseId) || typeof persistKeychain !== "boolean")
    throw new Error("Invalid credential operation.");
  return baseId + (persistKeychain ? ":keychain-v1" : ":transient-v1");
}
export function matchesStorageOperation(operation, submission) {
  if (typeof operation.persistKeychain !== "boolean" ||
      submission.persistKeychain !== operation.persistKeychain ||
      submission.operationId !== operation.id) return false;
  try {
    return operation.id === storageOperationId(operation.id.slice(0, 24), operation.persistKeychain);
  } catch { return false; }
}
