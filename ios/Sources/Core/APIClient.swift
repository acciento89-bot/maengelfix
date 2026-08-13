import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

enum APIError: LocalizedError {
    case invalidURL
    case transport(Error)
    case server(status: Int, message: String, code: String?)
    case decoding(Error)

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Die Serveradresse ist ungültig."
        case .transport(let error):
            return error.localizedDescription
        case .server(_, let message, _):
            return message
        case .decoding:
            return "Die Antwort des Servers konnte nicht verarbeitet werden."
        }
    }
}

private struct APIErrorPayload: Decodable {
    let error: String?
    let code: String?
}

final class APIClient: @unchecked Sendable {
    static let shared = APIClient()

    let baseURL: URL
    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    init(
        baseURL: URL = URL(string: "https://maengelfix.kamilunavo.com")!,
        session: URLSession? = nil
    ) {
        self.baseURL = baseURL

        if let session {
            self.session = session
        } else {
            let configuration = URLSessionConfiguration.default
            configuration.httpCookieStorage = .shared
            configuration.httpShouldSetCookies = true
            configuration.timeoutIntervalForRequest = 30
            configuration.timeoutIntervalForResource = 60
            self.session = URLSession(configuration: configuration)
        }

        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        self.decoder = decoder
        self.encoder = JSONEncoder()
    }

    func login(email: String, password: String) async throws -> User {
        let response: UserResponse = try await request(
            "/api/auth/login",
            method: "POST",
            body: LoginRequest(email: email, password: password)
        )
        return response.user
    }

    func register(name: String, email: String, password: String) async throws -> User {
        let response: UserResponse = try await request(
            "/api/auth/register",
            method: "POST",
            body: RegisterRequest(name: name, email: email, password: password)
        )
        return response.user
    }

    func me() async throws -> User {
        let response: UserResponse = try await request("/api/me")
        return response.user
    }

    func logout() async throws {
        try await requestWithoutResponse("/api/auth/logout", method: "POST")
    }

    func entitlements() async throws -> Entitlements {
        try await request("/api/entitlements")
    }

    func cases() async throws -> [DefectCase] {
        let response: CasesResponse = try await request("/api/cases")
        return response.cases
    }

    func caseDetail(id: String) async throws -> CaseDetailResponse {
        try await request("/api/cases/\(id)")
    }

    func createCase(_ input: CreateCaseRequest) async throws -> DefectCase {
        let response: CaseResponse = try await request("/api/cases", method: "POST", body: input)
        return response.caseItem
    }

    private func request<Response: Decodable>(
        _ path: String,
        method: String = "GET"
    ) async throws -> Response {
        try await perform(path: path, method: method, bodyData: nil)
    }

    private func request<Body: Encodable, Response: Decodable>(
        _ path: String,
        method: String,
        body: Body
    ) async throws -> Response {
        let data = try encoder.encode(body)
        return try await perform(path: path, method: method, bodyData: data)
    }

    private func requestWithoutResponse(_ path: String, method: String) async throws {
        let request = try makeRequest(path: path, method: method, bodyData: nil)
        let data: Data
        let response: URLResponse

        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.transport(error)
        }

        try validate(response: response, data: data)
    }

    private func perform<Response: Decodable>(
        path: String,
        method: String,
        bodyData: Data?
    ) async throws -> Response {
        let request = try makeRequest(path: path, method: method, bodyData: bodyData)

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.transport(error)
        }

        try validate(response: response, data: data)

        do {
            return try decoder.decode(Response.self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    private func makeRequest(path: String, method: String, bodyData: Data?) throws -> URLRequest {
        guard let url = URL(string: path, relativeTo: baseURL)?.absoluteURL else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("MängelFix-iOS/0.1", forHTTPHeaderField: "X-MaengelFix-Client")

        if let bodyData {
            request.httpBody = bodyData
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }

        return request
    }

    private func validate(response: URLResponse, data: Data) throws {
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.server(status: 0, message: "Ungültige Serverantwort.", code: nil)
        }

        guard (200..<300).contains(httpResponse.statusCode) else {
            let payload = try? decoder.decode(APIErrorPayload.self, from: data)
            let fallback = HTTPURLResponse.localizedString(forStatusCode: httpResponse.statusCode)
            throw APIError.server(
                status: httpResponse.statusCode,
                message: payload?.error ?? fallback,
                code: payload?.code
            )
        }
    }
}

private struct LoginRequest: Encodable {
    let email: String
    let password: String
}

private struct RegisterRequest: Encodable {
    let name: String
    let email: String
    let password: String
}
