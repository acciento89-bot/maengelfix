import Foundation
import StoreKit
final class APIClient {
 func verifyAppleTransaction(transactionID:String) async throws->Bool { ProviderProbe.calls.append("serverVerify"); return true }
}
@main struct Smoke {
 @MainActor static func main() async {
  let manager=StoreKitManager(), api=APIClient(), user="11111111-1111-4111-8111-111111111111"
  await manager.loadProducts()
  _=try? await manager.purchase(Product(),userID:user,api:api)
  _=try? await manager.restore(userID:user,api:api)
  await manager.refreshLocalEntitlements()
  for _ in 0..<30 {await Task.yield()}
  let expected=ProcessInfo.processInfo.environment["EXPECT_PROVIDER_CALLS"]=="1"
  if expected {
   for call in ["updates","products","purchase","sync","entitlements"] {precondition(ProviderProbe.calls.contains(call),"ordinary provider behavior lost: \(call)")}
  } else {
   precondition(ProviderProbe.calls.isEmpty,"native QA reached provider: \(ProviderProbe.calls)")
   precondition(manager.products.isEmpty && manager.activeProductIDs.isEmpty,"QA must not grant access")
  }
  print(expected ? "ordinary fake-provider route preserved" : "isolated fake-provider route zero calls, no access grant")
 }
}
