import SwiftUI

struct AuthView: View {
    private enum Mode: String, CaseIterable {
        case login = "Anmelden"
        case register = "Registrieren"
    }

    @Environment(AppSession.self) private var session
    @State private var mode: Mode = .login
    @State private var name = ""
    @State private var email = ""
    @State private var password = ""
    @State private var isSubmitting = false
    @State private var errorMessage: String?

    var body: some View {
        ScrollView {
            VStack(spacing: 28) {
                MFLogo()
                    .padding(.top, 42)

                VStack(spacing: 8) {
                    Text(mode == .login ? "Willkommen zurück" : "MängelFix Konto erstellen")
                        .font(.largeTitle.bold())
                        .multilineTextAlignment(.center)
                    Text("Deine Vorgänge sind mit demselben Konto wie auf maengelfix.kamilunavo.com verfügbar.")
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                }

                Picker("Modus", selection: $mode) {
                    ForEach(Mode.allCases, id: \.self) { item in
                        Text(item.rawValue).tag(item)
                    }
                }
                .pickerStyle(.segmented)

                VStack(spacing: 14) {
                    if mode == .register {
                        TextField("Name", text: $name)
                            .textContentType(.name)
                            .textFieldStyle(.roundedBorder)
                    }

                    TextField("E-Mail", text: $email)
                        .textContentType(.username)
                        .keyboardType(.emailAddress)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .textFieldStyle(.roundedBorder)

                    SecureField("Passwort", text: $password)
                        .textContentType(mode == .login ? .password : .newPassword)
                        .textFieldStyle(.roundedBorder)
                }

                if let errorMessage {
                    Text(errorMessage)
                        .font(.footnote)
                        .foregroundStyle(.red)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }

                Button {
                    submit()
                } label: {
                    HStack {
                        if isSubmitting { ProgressView().tint(.white) }
                        Text(mode.rawValue)
                            .fontWeight(.bold)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 13)
                }
                .buttonStyle(.borderedProminent)
                .tint(.mfPrimary)
                .disabled(isSubmitting || !formIsValid)

                Text("MängelFix ist ein Organisations- und Dokumentationstool und ersetzt keine Rechtsberatung.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }
            .padding(.horizontal, 24)
            .frame(maxWidth: 520)
            .frame(maxWidth: .infinity)
        }
        .background(Color.mfBackground)
    }

    private var formIsValid: Bool {
        let base = email.contains("@") && password.count >= 8
        return mode == .login ? base : base && !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    private func submit() {
        guard formIsValid else { return }
        errorMessage = nil
        isSubmitting = true

        Task {
            defer { isSubmitting = false }
            do {
                switch mode {
                case .login:
                    try await session.login(email: email, password: password)
                case .register:
                    try await session.register(name: name, email: email, password: password)
                }
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }
}
