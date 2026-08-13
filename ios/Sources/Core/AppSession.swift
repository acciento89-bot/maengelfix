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

    init(api: APIClient = .shared) {
        self.api = api
    }

    func restoreIfNeeded() async {
        guard phase == .loading else { return }

        do {
            user = try await api.me()
            phase = .signedIn
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
    }

    func register(name: String, email: String, password: String) async throws {
        user = try await api.register(name: name, email: email, password: password)
        phase = .signedIn
    }

    func refreshUser() async {
        guard phase == .signedIn else { return }
        user = try? await api.me()
    }

    func logout() async {
        try? await api.logout()
        user = nil
        phase = .signedOut
    }
}
