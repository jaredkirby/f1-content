// Dedicated local helper. Secret bytes use pipes only, never command arguments.
// File-based login Keychain supports command-line tools without app entitlements.
import Foundation
import Security
import Darwin

func fail(_ status: OSStatus = -50) -> Never {
    fputs("Keychain operation unavailable (status \(status)).\n", stderr)
    exit(2)
}
let args = Array(CommandLine.arguments.dropFirst())
guard args.count == 1 || args.count == 3 else { fail() }
let action = args[0]
guard ["store", "read", "status", "delete"].contains(action) else { fail() }
var service = "org.f1-content.openrouter"
if args.count == 3 {
    guard args[1] == "--test-id", UUID(uuidString: args[2]) != nil else { fail() }
    service = "org.f1-content.test." + args[2]
}
let account = "openrouter"
// Never trigger a hidden password dialog or unlock/change the user's Keychain.
SecKeychainSetUserInteractionAllowed(false)
var keychain: SecKeychain?
let keychainPath = NSHomeDirectory() + "/Library/Keychains/login.keychain-db"
let opened = SecKeychainOpen(keychainPath, &keychain)
guard opened == errSecSuccess, let keychain else { fail(opened) }
var item: SecKeychainItem?
let found = SecKeychainFindGenericPassword(keychain, UInt32(service.utf8.count), service,
                                         UInt32(account.utf8.count), account, nil, nil, &item)
if action == "status" {
    guard found == errSecSuccess || found == errSecItemNotFound else { fail(found) }
    print(found == errSecSuccess ? "{\"status\":\"available\"}" : "{\"status\":\"missing\"}")
} else if action == "store" {
    guard isatty(STDIN_FILENO) == 0 else { fail() }
    let data = FileHandle.standardInput.readData(ofLength: 513)
    guard !data.isEmpty, data.count <= 512, data.allSatisfy({ $0 >= 33 && $0 <= 126 }) else { fail() }
    let status = data.withUnsafeBytes { bytes -> OSStatus in
        if found == errSecSuccess, let item {
            return SecKeychainItemModifyAttributesAndData(item, nil, UInt32(data.count), bytes.baseAddress)
        }
        guard found == errSecItemNotFound else { return found }
        // Default item ACL trusts its creating executable, never all applications.
        return SecKeychainAddGenericPassword(keychain, UInt32(service.utf8.count), service,
             UInt32(account.utf8.count), account, UInt32(data.count), bytes.baseAddress!, nil)
    }
    guard status == errSecSuccess else { fail(status) }
    print("{\"status\":\"stored\"}")
} else if action == "read" {
    guard isatty(STDOUT_FILENO) == 0 else { fail() }
    var length: UInt32 = 0
    var bytes: UnsafeMutableRawPointer?
    let status = SecKeychainFindGenericPassword(keychain, UInt32(service.utf8.count), service,
                       UInt32(account.utf8.count), account, &length, &bytes, nil)
    guard status == errSecSuccess, let bytes else { fail(status) }
    guard length > 0 && length <= 512 else {
        SecKeychainItemFreeContent(nil, bytes); fail()
    }
    FileHandle.standardOutput.write(Data(bytes: bytes, count: Int(length)))
    memset(bytes, 0, Int(length))
    SecKeychainItemFreeContent(nil, bytes)
} else {
    if found == errSecItemNotFound { print("{\"status\":\"missing\"}") }
    else {
        guard found == errSecSuccess, let item else { fail(found) }
        let status = SecKeychainItemDelete(item)
        guard status == errSecSuccess else { fail(status) }
        print("{\"status\":\"deleted\"}")
    }
}
