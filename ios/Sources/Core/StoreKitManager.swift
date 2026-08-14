import Foundation
import Observation
import StoreKit

@MainActor
@Observable
final class StoreKitManager {
    static let privateMonthlyProductID = "com.kamilunavo.maengelfix.privatepro.monthly"
    static let privateYearlyProductID = "com.kamilunavo.maengelfix.privatepro.yearly"

    // Compatibility aliases for existing private-subscription UI.
    static let monthlyProductID = privateMonthlyProductID
    static let yearlyProductID = privateYearlyProductID

    static let managementStarterMonthlyProductID = "com.kamilunavo.maengelfix.managementstarter.monthly"
    static let managementStarterYearlyProductID = "com.kamilunavo.maengelfix.managementstarter.yearly"
    static let managementProMonthlyProductID = "com.kamilunavo.maengelfix.managementpro.monthly"
    static let managementProYearlyProductID = "com.kamilunavo.maengelfix.managementpro.yearly"
    static let managementBusinessMonthlyProductID = "com.kamilunavo.maengelfix.managementbusiness.monthly"
    static let managementBusinessYearlyProductID = "com.kamilunavo.maengelfix.managementbusiness.yearly"

    static let privateProductIDs: Set<String> = [
        privateMonthlyProductID,
        privateYearlyProductID
    ]

    static let managementProductIDs: Set<String> = [
        managementStarterMonthlyProductID,
        managementStarterYearlyProductID,
        managementProMonthlyProductID,
        managementProYearlyProductID,
        managementBusinessMonthlyProductID,
        managementBusinessYearlyProductID
    ]

    static let productIDs: Set<String> = privateProductIDs.union(managementProductIDs)

    var products: [Product] = []
    var isLoading = false
    var isPurchasing = false
    var errorMessage: String?
    var activeProductIDs: Set<String> = []

    var activeProductID: String? { activeProductIDs.first }

    var privateProducts: [Product] {
        products
            .filter { Self.privateProductIDs.contains($0.id) }
            .sorted { Self.sortIndex(for: $0.id) < Self.sortIndex(for: $1.id) }
    }

    var managementProducts: [Product] {
        products
            .filter { Self.managementProductIDs.contains($0.id) }
            .sorted { Self.sortIndex(for: $0.id) < Self.sortIndex(for: $1.id) }
    }

    private nonisolated(unsafe) var updatesTask: Task<Void, Never>?

    init() {
        updatesTask = Task { [weak self] in
            for await result in Transaction.updates {
                guard let self else { return }
                guard case .verified(let transaction) = result else { continue }
                if Self.productIDs.contains(transaction.productID) {
                    await self.refreshLocalEntitlements()
                }
            }
        }
    }

    deinit {
        updatesTask?.cancel()
    }

    func loadProducts() async {
        guard products.isEmpty else { return }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            products = try await Product.products(for: Array(Self.productIDs))
                .sorted { Self.sortIndex(for: $0.id) < Self.sortIndex(for: $1.id) }
            await refreshLocalEntitlements()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func purchase(_ product: Product, userID: String, api: APIClient) async throws -> Bool {
        guard let accountToken = UUID(uuidString: userID) else {
            throw StoreKitManagerError.invalidAccountIdentifier
        }

        isPurchasing = true
        errorMessage = nil
        defer { isPurchasing = false }

        let result = try await product.purchase(options: [.appAccountToken(accountToken)])
        switch result {
        case .success(let verification):
            guard case .verified(let transaction) = verification else {
                throw StoreKitManagerError.unverifiedTransaction
            }
            _ = try await api.verifyAppleTransaction(transactionID: String(transaction.id))
            await transaction.finish()
            await refreshLocalEntitlements(accountToken: accountToken)
            return true
        case .pending:
            throw StoreKitManagerError.pending
        case .userCancelled:
            return false
        @unknown default:
            throw StoreKitManagerError.unknown
        }
    }

    func restore(userID: String, api: APIClient) async throws -> Bool {
        guard let accountToken = UUID(uuidString: userID) else {
            throw StoreKitManagerError.invalidAccountIdentifier
        }

        isPurchasing = true
        errorMessage = nil
        defer { isPurchasing = false }

        // StoreKit already maintains the current entitlements. Read them first so an
        // existing TestFlight/App-Store subscription can be linked to MängelFix without
        // forcing AppStore.sync(), which can fail independently of the purchase itself.
        if try await verifyCurrentEntitlements(accountToken: accountToken, api: api) {
            await refreshLocalEntitlements(accountToken: accountToken)
            return true
        }

        // Only ask StoreKit for a forced sync when no entitlement for this MängelFix
        // account is available locally.
        try await AppStore.sync()
        let restored = try await verifyCurrentEntitlements(accountToken: accountToken, api: api)
        await refreshLocalEntitlements(accountToken: accountToken)
        return restored
    }

    private func verifyCurrentEntitlements(accountToken: UUID, api: APIClient) async throws -> Bool {
        var restored = false
        for await result in Transaction.currentEntitlements {
            guard case .verified(let transaction) = result,
                  Self.productIDs.contains(transaction.productID),
                  transaction.revocationDate == nil else { continue }
            if let expirationDate = transaction.expirationDate, expirationDate <= Date() { continue }

            // Every MängelFix purchase is made with the UUID of the signed-in account.
            // This prevents a different MängelFix account using the same Apple ID from
            // accidentally receiving the wrong subscription during restore.
            guard transaction.appAccountToken == accountToken else { continue }

            _ = try await api.verifyAppleTransaction(transactionID: String(transaction.id))
            restored = true
        }
        return restored
    }

    func refreshLocalEntitlements(accountToken: UUID? = nil) async {
        var active: Set<String> = []
        for await result in Transaction.currentEntitlements {
            guard case .verified(let transaction) = result,
                  Self.productIDs.contains(transaction.productID),
                  transaction.revocationDate == nil else { continue }
            if let expirationDate = transaction.expirationDate, expirationDate <= Date() { continue }
            if let accountToken, transaction.appAccountToken != accountToken { continue }
            active.insert(transaction.productID)
        }
        activeProductIDs = active
    }

    func isProductActive(_ productID: String) -> Bool {
        activeProductIDs.contains(productID)
    }

    static func managementTitle(for productID: String) -> String {
        switch productID {
        case managementStarterMonthlyProductID, managementStarterYearlyProductID:
            return "Verwaltung Starter"
        case managementProMonthlyProductID, managementProYearlyProductID:
            return "Verwaltung Pro"
        case managementBusinessMonthlyProductID, managementBusinessYearlyProductID:
            return "Verwaltung Business"
        default:
            return "MängelFix Verwaltung"
        }
    }

    static func periodLabel(for productID: String) -> String {
        productID.hasSuffix(".yearly") ? "Jährlich" : "Monatlich"
    }

    private static func sortIndex(for productID: String) -> Int {
        switch productID {
        case privateMonthlyProductID: return 0
        case privateYearlyProductID: return 1
        case managementStarterMonthlyProductID: return 10
        case managementStarterYearlyProductID: return 11
        case managementProMonthlyProductID: return 20
        case managementProYearlyProductID: return 21
        case managementBusinessMonthlyProductID: return 30
        case managementBusinessYearlyProductID: return 31
        default: return 999
        }
    }
}

enum StoreKitManagerError: LocalizedError {
    case invalidAccountIdentifier
    case unverifiedTransaction
    case pending
    case unknown

    var errorDescription: String? {
        switch self {
        case .invalidAccountIdentifier:
            return "Dein MängelFix-Konto kann nicht mit dem App-Store-Kauf verknüpft werden."
        case .unverifiedTransaction:
            return "Der App-Store-Kauf konnte nicht verifiziert werden."
        case .pending:
            return "Der Kauf wartet noch auf eine Freigabe durch den App Store."
        case .unknown:
            return "Der App-Store-Kauf konnte nicht abgeschlossen werden."
        }
    }
}
