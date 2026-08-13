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
        case .invalidURL: return "Die Serveradresse ist ungültig."
        case .transport(let error): return error.localizedDescription
        case .server(_, let message, _): return message
        case .decoding: return "Die Antwort des Servers konnte nicht verarbeitet werden."
        }
    }

    var code: String? {
        if case .server(_, _, let code) = self { return code }
        return nil
    }
}

private struct APIErrorPayload: Decodable {
    let error: String?
    let code: String?
}

struct UploadFile: Sendable {
    let data: Data
    let fileName: String
    let mimeType: String
}

final class APIClient: @unchecked Sendable {
    static let shared = APIClient()

    let baseURL: URL
    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    init(baseURL: URL = URL(string: "https://maengelfix.kamilunavo.com")!, session: URLSession? = nil) {
        self.baseURL = baseURL
        if let session {
            self.session = session
        } else {
            let configuration = URLSessionConfiguration.default
            configuration.httpCookieStorage = .shared
            configuration.httpShouldSetCookies = true
            configuration.timeoutIntervalForRequest = 45
            configuration.timeoutIntervalForResource = 120
            self.session = URLSession(configuration: configuration)
        }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        self.decoder = decoder
        self.encoder = JSONEncoder()
    }

    func login(email: String, password: String) async throws -> User {
        let response: UserResponse = try await request("/api/auth/login", method: "POST", body: LoginRequest(email: email, password: password))
        return response.user
    }

    func register(name: String, email: String, password: String) async throws -> User {
        let response: UserResponse = try await request("/api/auth/register", method: "POST", body: RegisterRequest(name: name, email: email, password: password))
        return response.user
    }

    func forgotPassword(email: String) async throws -> String {
        let response: SimpleResponse = try await request("/api/auth/forgot-password", method: "POST", body: EmailRequest(email: email))
        return response.message ?? "Wenn ein Konto existiert, wurde eine E-Mail versendet."
    }

    func resendVerification() async throws -> SimpleResponse {
        try await request("/api/auth/resend-verification", method: "POST", body: EmptyRequest())
    }

    func me() async throws -> User {
        let response: UserResponse = try await request("/api/me")
        return response.user
    }

    func updateProfile(_ input: UpdateProfileRequest) async throws -> User {
        let response: UserResponse = try await request("/api/profile", method: "PATCH", body: input)
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

    func updateCase(id: String, input: UpdateCaseRequest) async throws -> DefectCase {
        let response: CaseResponse = try await request("/api/cases/\(id)", method: "PATCH", body: input)
        return response.caseItem
    }

    func sendMessage(caseID: String, message: String) async throws -> CaseMessage {
        let response: MessageResponse = try await request("/api/cases/\(caseID)/messages", method: "POST", body: MessageRequest(message: message))
        return response.message
    }

    func uploadImages(caseID: String, files: [UploadFile]) async throws -> [CaseAttachment] {
        guard !files.isEmpty else { return [] }
        let boundary = "Boundary-\(UUID().uuidString)"
        var body = Data()
        for file in files.prefix(5) {
            body.appendUTF8("--\(boundary)\r\n")
            body.appendUTF8("Content-Disposition: form-data; name=\"images\"; filename=\"\(file.fileName.replacingOccurrences(of: "\"", with: ""))\"\r\n")
            body.appendUTF8("Content-Type: \(file.mimeType)\r\n\r\n")
            body.append(file.data)
            body.appendUTF8("\r\n")
        }
        body.appendUTF8("--\(boundary)--\r\n")

        var request = try makeRequest(path: "/api/cases/\(caseID)/attachments", method: "POST", bodyData: nil)
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.httpBody = body
        let (data, response) = try await data(for: request)
        try validate(response: response, data: data)
        do { return try decoder.decode(AttachmentsResponse.self, from: data).attachments }
        catch { throw APIError.decoding(error) }
    }

    func attachmentData(id: String) async throws -> Data {
        try await rawData("/api/attachments/\(id)")
    }

    func casePDFData(id: String) async throws -> Data {
        try await rawData("/api/cases/\(id)/pdf")
    }

    private func rawData(_ path: String) async throws -> Data {
        let request = try makeRequest(path: path, method: "GET", bodyData: nil)
        let (data, response) = try await data(for: request)
        try validate(response: response, data: data)
        return data
    }

    private func request<Response: Decodable>(_ path: String, method: String = "GET") async throws -> Response {
        try await perform(path: path, method: method, bodyData: nil)
    }

    private func request<Body: Encodable, Response: Decodable>(_ path: String, method: String, body: Body) async throws -> Response {
        let data = try encoder.encode(body)
        return try await perform(path: path, method: method, bodyData: data)
    }

    private func requestWithoutResponse(_ path: String, method: String) async throws {
        let request = try makeRequest(path: path, method: method, bodyData: nil)
        let (data, response) = try await data(for: request)
        try validate(response: response, data: data)
    }

    private func perform<Response: Decodable>(path: String, method: String, bodyData: Data?) async throws -> Response {
        let request = try makeRequest(path: path, method: method, bodyData: bodyData)
        let (data, response) = try await data(for: request)
        try validate(response: response, data: data)
        do { return try decoder.decode(Response.self, from: data) }
        catch { throw APIError.decoding(error) }
    }

    private func data(for request: URLRequest) async throws -> (Data, URLResponse) {
        do { return try await session.data(for: request) }
        catch { throw APIError.transport(error) }
    }

    private func makeRequest(path: String, method: String, bodyData: Data?) throws -> URLRequest {
        guard let url = URL(string: path, relativeTo: baseURL)?.absoluteURL else { throw APIError.invalidURL }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("MängelFix-iOS/0.2", forHTTPHeaderField: "X-MaengelFix-Client")
        if let bodyData {
            request.httpBody = bodyData
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        return request
    }

    private func validate(response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else { throw APIError.server(status: 0, message: "Ungültige Serverantwort.", code: nil) }
        guard (200..<300).contains(http.statusCode) else {
            let payload = try? decoder.decode(APIErrorPayload.self, from: data)
            throw APIError.server(status: http.statusCode, message: payload?.error ?? HTTPURLResponse.localizedString(forStatusCode: http.statusCode), code: payload?.code)
        }
    }
}

private struct LoginRequest: Encodable { let email: String; let password: String }
private struct RegisterRequest: Encodable { let name: String; let email: String; let password: String }
private struct EmailRequest: Encodable { let email: String }
private struct MessageRequest: Encodable { let message: String }
private struct EmptyRequest: Encodable {}

private extension Data {
    mutating func appendUTF8(_ string: String) {
        if let data = string.data(using: .utf8) { append(data) }
    }
}
