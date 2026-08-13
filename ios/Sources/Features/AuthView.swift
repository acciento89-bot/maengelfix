import SwiftUI

struct AuthView: View {
    private enum Mode: String, CaseIterable { case login = "Anmelden"; case register = "Registrieren" }
    @Environment(AppSession.self) private var session
    @State private var mode: Mode = .login
    @State private var name = ""
    @State private var email = ""
    @State private var password = ""
    @State private var isSubmitting = false
    @State private var errorMessage: String?
    @State private var showForgot = false

    var body: some View {
        ScrollView {
            VStack(spacing: 26) {
                MFLogo().padding(.top, 42)
                VStack(spacing: 8) {
                    Text(mode == .login ? "Willkommen zurück" : "MängelFix Konto erstellen")
                        .font(.largeTitle.bold()).multilineTextAlignment(.center)
                    Text("Deine Vorgänge sind mit demselben Konto wie im Web verfügbar.")
                        .foregroundStyle(.secondary).multilineTextAlignment(.center)
                }
                Picker("Modus", selection: $mode) {
                    ForEach(Mode.allCases, id: \.self) { Text($0.rawValue).tag($0) }
                }.pickerStyle(.segmented)
                VStack(spacing: 14) {
                    if mode == .register {
                        TextField("Name", text: $name).textContentType(.name).textFieldStyle(.roundedBorder)
                    }
                    TextField("E-Mail", text: $email)
                        .textContentType(.username).keyboardType(.emailAddress)
                        .textInputAutocapitalization(.never).autocorrectionDisabled().textFieldStyle(.roundedBorder)
                    SecureField("Passwort", text: $password)
                        .textContentType(mode == .login ? .password : .newPassword).textFieldStyle(.roundedBorder)
                }
                if let errorMessage {
                    Text(errorMessage).font(.footnote).foregroundStyle(.red).frame(maxWidth: .infinity, alignment: .leading)
                }
                Button { submit() } label: {
                    HStack {
                        if isSubmitting { ProgressView().tint(.white) }
                        Text(mode.rawValue).fontWeight(.bold)
                    }.frame(maxWidth: .infinity).padding(.vertical, 13)
                }
                .buttonStyle(.borderedProminent).disabled(isSubmitting || !formIsValid)

                if mode == .login {
                    Button("Passwort vergessen?") { showForgot = true }.font(.subheadline)
                }

                Text("MängelFix ist ein Organisations- und Dokumentationstool und ersetzt keine Rechtsberatung.")
                    .font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.center)
            }
            .padding(.horizontal, 24).frame(maxWidth: 520).frame(maxWidth: .infinity)
        }
        .background(Color.mfBackground)
        .sheet(isPresented: $showForgot) { ForgotPasswordView(initialEmail: email) }
    }

    private var formIsValid: Bool {
        let base = email.contains("@") && password.count >= 8
        return mode == .login ? base : base && !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    private func submit() {
        guard formIsValid else { return }
        errorMessage = nil; isSubmitting = true
        Task {
            do {
                if mode == .login { try await session.login(email: email, password: password) }
                else { try await session.register(name: name, email: email, password: password) }
            } catch { errorMessage = error.localizedDescription }
            isSubmitting = false
        }
    }
}

private struct ForgotPasswordView: View {
    @Environment(AppSession.self) private var session
    @Environment(\.dismiss) private var dismiss
    @State private var email: String
    @State private var message: String?
    @State private var isSending = false

    init(initialEmail: String) { _email = State(initialValue: initialEmail) }

    var body: some View {
        NavigationStack {
            Form {
                Section("Passwort zurücksetzen") {
                    TextField("E-Mail", text: $email).keyboardType(.emailAddress).textInputAutocapitalization(.never)
                    Text("Du erhältst einen Link per E-Mail, sofern ein Konto existiert.").font(.caption).foregroundStyle(.secondary)
                }
                if let message { Section { Text(message) } }
                Section {
                    Button("Link anfordern") { Task { await send() } }.disabled(!email.contains("@") || isSending)
                }
            }
            .navigationTitle("Passwort vergessen")
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Schließen") { dismiss() } } }
        }
    }

    @MainActor private func send() async {
        isSending = true
        do { message = try await session.api.forgotPassword(email: email) }
        catch { message = error.localizedDescription }
        isSending = false
    }
}
