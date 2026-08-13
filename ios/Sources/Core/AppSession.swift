import Foundation
import Observation

@MainActor
@Observable
final class AppSession {
    enum Phase {
        case loading
        case signedOut
        case signedIn
    }

    let api: APIClient
    var phase: Phase = .loading
    var user: User?
    var entitlements: Entitlements?

    var isManagement: Bool {
        entitlements?.scope == "organization" || user?.onboardingUseCase == "management"
    }

    init(api: APIClient = .shared) {
        self.api = api
    }

    func restoreIfNeeded() async {
        guard phase == .loading else { return }

        do {
            user = try await api.me()
            phase = .signedIn
            await refreshEntitlements()
        } catch let error as APIError {
            if case .server(let status, _, _) = error, status == 401 {
                user = nil
                phase = .signedOut
            } else {
                user = nil
                phase = .signedOut
            }
        } catch {
            user = nil
            phase = .signedOut
        }
    }

    func login(email: String, password: String) async throws {
        user = try await api.login(email: email, password: password)
        phase = .signedIn
        await refreshEntitlements()
    }

    func register(name: String, email: String, password: String, accountType: String, organizationName: String?) async throws {
        user = try await api.register(name: name, email: email, password: password, accountType: accountType, organizationName: organizationName)
        phase = .signedIn
        await refreshEntitlements()
    }

    func refreshEntitlements() async {
        guard phase == .signedIn else { entitlements = nil; return }
        entitlements = try? await api.entitlements()
    }

    func refreshUser() async {
        guard phase == .signedIn else { return }
        user = try? await api.me()
    }

    func logout() async {
        try? await api.logout()
        user = nil
        entitlements = nil
        phase = .signedOut
    }
}
