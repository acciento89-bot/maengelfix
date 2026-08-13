import SwiftUI

struct AuthView: View {
    private enum Mode: String, CaseIterable { case login = "Anmelden"; case register = "Registrieren" }
    private enum AccountKind: String, CaseIterable, Identifiable {
        case privateAccount = "private"
        case management = "management"
        var id: String { rawValue }
        var label: String { self == .privateAccount ? "Privat" : "Hausverwaltung" }
    }

    @Environment(AppSession.self) private var session
    @State private var mode: Mode = .login
    @State private var accountKind: AccountKind = .privateAccount
    @State private var name = ""
    @State private var organizationName = ""
    @State private var email = ""
    @State private var password = ""
    @State private var isSubmitting = false
    @State private var errorMessage: String?
    @State private var showForgot = false

    private var isManagementRegistration: Bool { mode == .register && accountKind == .management }

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                MFLogo().padding(.top, 34)
                VStack(spacing: 8) {
                    Text(title)
                        .font(.largeTitle.bold()).multilineTextAlignment(.center)
                    Text(subtitle)
                        .foregroundStyle(.secondary).multilineTextAlignment(.center)
                }

                Picker("Modus", selection: $mode) {
                    ForEach(Mode.allCases, id: \.self) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented)

                if mode == .register {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Wie möchtest du MängelFix nutzen?")
                            .font(.headline)
                        Picker("Kontotyp", selection: $accountKind) {
                            ForEach(AccountKind.allCases) { kind in Text(kind.label).tag(kind) }
                        }
                        .pickerStyle(.segmented)

                        if isManagementRegistration {
                            Label("14 Tage alle Verwaltungsfunktionen kostenlos testen", systemImage: "checkmark.seal.fill")
                                .font(.footnote.weight(.semibold))
                                .foregroundStyle(Color.mfPrimary)
                        } else {
                            Text("Privat Free bleibt dauerhaft kostenlos. Privat Pro kannst du später optional aktivieren.")
                                .font(.footnote)
                                .foregroundStyle(.secondary)
                        }
                    }
                }

                VStack(spacing: 14) {
                    if mode == .register {
                        TextField(isManagementRegistration ? "Dein Name" : "Name", text: $name)
                            .textContentType(.name).textFieldStyle(.roundedBorder)
                        if isManagementRegistration {
                            TextField("Name der Hausverwaltung", text: $organizationName)
                                .textContentType(.organizationName).textFieldStyle(.roundedBorder)
                        }
                    }
                    TextField("E-Mail", text: $email)
                        .textContentType(.username).keyboardType(.emailAddress)
                        .textInputAutocapitalization(.never).autocorrectionDisabled().textFieldStyle(.roundedBorder)
                    SecureField("Passwort", text: $password)
                        .textContentType(mode == .login ? .password : .newPassword).textFieldStyle(.roundedBorder)
                }

                if isManagementRegistration {
                    MFCard {
                        VStack(alignment: .leading, spacing: 5) {
                            Text("Verwaltungs-Testphase").font(.headline)
                            Text("Keine Zahlung bei der Registrierung. Nach 14 Tagen wählst du den passenden Verwaltungstarif.")
                                .font(.footnote).foregroundStyle(.secondary)
                        }
                    }
                }

                if let errorMessage {
                    Text(errorMessage).font(.footnote).foregroundStyle(.red).frame(maxWidth: .infinity, alignment: .leading)
                }

                Button { submit() } label: {
                    HStack {
                        if isSubmitting { ProgressView().tint(.white) }
                        Text(buttonTitle).fontWeight(.bold)
                    }.frame(maxWidth: .infinity).padding(.vertical, 13)
                }
                .buttonStyle(.borderedProminent).disabled(isSubmitting || !formIsValid)

                if mode == .login {
                    Button("Passwort vergessen?") { showForgot = true }.font(.subheadline)
                }

                Text("MängelFix ist ein Organisations- und Dokumentationstool und ersetzt keine Rechtsberatung.")
                    .font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.center)
            }
            .padding(.horizontal, 24).frame(maxWidth: 540).frame(maxWidth: .infinity)
        }
        .background(Color.mfBackground)
        .sheet(isPresented: $showForgot) { ForgotPasswordView(initialEmail: email) }
    }

    private var title: String {
        if mode == .login { return "Willkommen zurück" }
        return isManagementRegistration ? "MängelFix Verwaltung starten" : "MängelFix Privat starten"
    }

    private var subtitle: String {
        if mode == .login { return "Deine Vorgänge sind mit demselben Konto wie im Web verfügbar." }
        return isManagementRegistration
            ? "Eigener Verwaltungs-Arbeitsbereich für Objekte, Mängel, Team und Fristen."
            : "Dein persönlicher Mängelordner für private Vorgänge."
    }

    private var buttonTitle: String {
        if mode == .login { return "Anmelden" }
        return isManagementRegistration ? "14 Tage kostenlos testen" : "Privatkonto erstellen"
    }

    private var formIsValid: Bool {
        let base = email.contains("@") && password.count >= 8
        guard mode == .register else { return base }
        let validName = !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        let validOrganization = !isManagementRegistration || !organizationName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        return base && validName && validOrganization
    }

    private func submit() {
        guard formIsValid else { return }
        errorMessage = nil; isSubmitting = true
        Task {
            do {
                if mode == .login {
                    try await session.login(email: email, password: password)
                } else {
                    try await session.register(
                        name: name,
                        email: email,
                        password: password,
                        accountType: accountKind.rawValue,
                        organizationName: isManagementRegistration ? organizationName : nil
                    )
                }
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
