import Foundation
import Observation
import StoreKit

@MainActor
@Observable
final class StoreKitManager {
    static let monthlyProductID = "com.kamilunavo.maengelfix.privatepro.monthly"
    static let yearlyProductID = "com.kamilunavo.maengelfix.privatepro.yearly"
    static let productIDs = [monthlyProductID, yearlyProductID]

    var products: [Product] = []
    var isLoading = false
    var isPurchasing = false
    var errorMessage: String?
    var activeProductID: String?

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
            products = try await Product.products(for: Self.productIDs)
                .sorted { lhs, rhs in
                    if lhs.id == Self.monthlyProductID { return true }
                    if rhs.id == Self.monthlyProductID { return false }
                    return lhs.displayPrice < rhs.displayPrice
                }
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
            await refreshLocalEntitlements()
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
        guard UUID(uuidString: userID) != nil else {
            throw StoreKitManagerError.invalidAccountIdentifier
        }

        try await AppStore.sync()
        var restored = false
        for await result in Transaction.currentEntitlements {
            guard case .verified(let transaction) = result,
                  Self.productIDs.contains(transaction.productID),
                  transaction.revocationDate == nil else { continue }
            _ = try await api.verifyAppleTransaction(transactionID: String(transaction.id))
            restored = true
        }
        await refreshLocalEntitlements()
        return restored
    }

    func refreshLocalEntitlements() async {
        activeProductID = nil
        for await result in Transaction.currentEntitlements {
            guard case .verified(let transaction) = result,
                  Self.productIDs.contains(transaction.productID),
                  transaction.revocationDate == nil else { continue }
            if let expirationDate = transaction.expirationDate, expirationDate <= Date() { continue }
            activeProductID = transaction.productID
            break
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
