from pathlib import Path

api_p = Path('ios/Sources/Core/APIClient.swift')
profile_p = Path('ios/Sources/Features/ProfileView.swift')
project_p = Path('ios/project.yml')

api = api_p.read_text()
profile = profile_p.read_text()
project = project_p.read_text()

# --- API: native account deletion ---
logout_anchor = '''    func logout() async throws {
        try await requestWithoutResponse("/api/auth/logout", method: "POST")
    }
'''
delete_api = '''    func deleteAccount(password: String, confirmation: String) async throws {
        let _: SimpleResponse = try await request(
            "/api/account",
            method: "DELETE",
            body: DeleteAccountRequest(password: password, confirmation: confirmation)
        )
    }

    func logout() async throws {
        try await requestWithoutResponse("/api/auth/logout", method: "POST")
    }
'''
if 'func deleteAccount(password:' not in api:
    if logout_anchor not in api:
        raise SystemExit('API logout anchor not found')
    api = api.replace(logout_anchor, delete_api, 1)

request_anchor = 'private struct AppleBillingResponse: Decodable { let user: User }\nprivate struct EmptyRequest: Encodable {}'
request_new = 'private struct AppleBillingResponse: Decodable { let user: User }\nprivate struct DeleteAccountRequest: Encodable { let password: String; let confirmation: String }\nprivate struct EmptyRequest: Encodable {}'
if 'private struct DeleteAccountRequest:' not in api:
    if request_anchor not in api:
        raise SystemExit('API request model anchor not found')
    api = api.replace(request_anchor, request_new, 1)

api_p.write_text(api)

# --- Profile: make deletion visible and complete inside the iOS app ---
state_anchor = '    @State private var billingMessage: String?\n'
if '@State private var showDeleteAccount = false' not in profile:
    if state_anchor not in profile:
        raise SystemExit('Profile state anchor not found')
    profile = profile.replace(state_anchor, state_anchor + '    @State private var showDeleteAccount = false\n', 1)

body_anchor = '''                    if session.isManagement {
                        managementSubscriptionSection(user: user)
                    } else {
                        subscriptionSection(user: user)
                    }
                }
'''
body_new = '''                    if session.isManagement {
                        managementSubscriptionSection(user: user)
                    } else {
                        subscriptionSection(user: user)
                    }

                    accountPrivacySection
                }
'''
if 'accountPrivacySection' not in profile:
    if body_anchor not in profile:
        raise SystemExit('Profile account section anchor not found')
    profile = profile.replace(body_anchor, body_new, 1)

sheet_anchor = '''            .sheet(isPresented: $showEdit) {
                if let user = session.user {
                    NavigationStack {
                        ProfileEditView(user: user) { updated in
                            session.user = updated
                            showEdit = false
                        }
                    }
                }
            }
'''
sheet_new = sheet_anchor + '''            .sheet(isPresented: $showDeleteAccount) {
                AccountDeletionView()
            }
'''
if '.sheet(isPresented: $showDeleteAccount)' not in profile:
    if sheet_anchor not in profile:
        raise SystemExit('Profile sheet anchor not found')
    profile = profile.replace(sheet_anchor, sheet_new, 1)

version_anchor = '    private var appVersionLabel: String {'
privacy_section = '''    @ViewBuilder
    private var accountPrivacySection: some View {
        Section {
            Link(destination: URL(string: "https://maengelfix.kamilunavo.com/datenschutz")!) {
                Label("Datenschutzerklärung", systemImage: "hand.raised")
            }
            Link(destination: URL(string: "https://maengelfix.kamilunavo.com/nutzungsbedingungen")!) {
                Label("Nutzungsbedingungen (EULA)", systemImage: "doc.text")
            }
            Button(role: .destructive) {
                showDeleteAccount = true
            } label: {
                Label("Konto dauerhaft löschen", systemImage: "trash")
            }
        } header: {
            Text("Konto & Datenschutz")
        } footer: {
            Text("Die Kontolöschung kann vollständig in MängelFix gestartet und bestätigt werden. Ein über Apple abgeschlossenes Abonnement wird separat in den Apple-Abonnementeinstellungen verwaltet.")
        }
    }

'''
if 'private var accountPrivacySection:' not in profile:
    if version_anchor not in profile:
        raise SystemExit('Profile version anchor not found')
    profile = profile.replace(version_anchor, privacy_section + version_anchor, 1)

# Replace the private subscription UI with an App-Review-complete explanation.
sub_start = profile.find('    @ViewBuilder\n    private func subscriptionSection(user: User) -> some View {')
sub_end = profile.find('    @MainActor private func buy(', sub_start)
if sub_start == -1 or sub_end == -1:
    raise SystemExit('Private subscription function boundaries not found')

new_subscription = '''    @ViewBuilder
    private func subscriptionSection(user: User) -> some View {
        Section {
            VStack(alignment: .leading, spacing: 10) {
                Text("Was du mit Privat Pro bekommst")
                    .font(.headline)
                Label("Unbegrenzt aktive Mängelvorgänge statt maximal 5 in Privat Free", systemImage: "checkmark.circle.fill")
                Label("Mehr als 3 Fotos sowie PDF-Dokumente und weitere Belege je Vorgang", systemImage: "checkmark.circle.fill")
                Label("Fristen, Aufgaben, Erinnerungen und Kalender", systemImage: "checkmark.circle.fill")
                Label("Suche & Archiv sowie persönliche Auswertungen", systemImage: "checkmark.circle.fill")
                Label("Übergabe- und Abnahmeprotokolle", systemImage: "checkmark.circle.fill")
            }
            .font(.subheadline)
            .foregroundStyle(.primary)
            .padding(.vertical, 4)

            if user.planCode == "private_pro" && ["active", "trialing"].contains(user.subscriptionStatus) {
                Label("Privat Pro ist aktiv", systemImage: "checkmark.seal.fill")
                    .foregroundStyle(Color.mfPrimary)
                if let end = user.subscriptionCurrentPeriodEnd, !end.isEmpty {
                    LabeledContent("Aktueller Zeitraum", value: end)
                }
                if store.activeProductIDs.contains(where: { StoreKitManager.privateProductIDs.contains($0) }) {
                    Button("App-Store-Abo verwalten") {
                        if let url = URL(string: "https://apps.apple.com/account/subscriptions") { openURL(url) }
                    }
                }
            } else if store.isLoading {
                HStack { ProgressView(); Text("App-Store-Angebote werden geladen …") }
            } else if store.privateProducts.isEmpty {
                Text("Die App-Store-Abos werden verfügbar, sobald sie in App Store Connect freigeschaltet sind.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            } else {
                ForEach(store.privateProducts, id: \.id) { product in
                    Button {
                        Task { await buy(product, user: user) }
                    } label: {
                        HStack(alignment: .center, spacing: 12) {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(product.id == StoreKitManager.privateYearlyProductID ? "Privat Pro – jährlich" : "Privat Pro – monatlich")
                                    .font(.headline)
                                    .foregroundStyle(.primary)
                                Text(product.id == StoreKitManager.privateYearlyProductID ? "Laufzeit: 1 Jahr · automatische Verlängerung" : "Laufzeit: 1 Monat · automatische Verlängerung")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            Spacer()
                            Text(product.displayPrice)
                                .fontWeight(.semibold)
                                .foregroundStyle(.primary)
                        }
                    }
                    .disabled(store.isPurchasing)
                }
            }

            Button("Käufe wiederherstellen") {
                Task { await restorePurchases(user: user) }
            }
            .disabled(store.isPurchasing)

            if store.isPurchasing {
                HStack { ProgressView(); Text("App Store wird verarbeitet …") }
            }
            if let billingMessage {
                Text(billingMessage).font(.footnote).foregroundStyle(.secondary)
            }

            Text("Das Abonnement verlängert sich automatisch um die gewählte Laufzeit, bis es in den Apple-Abonnementeinstellungen gekündigt wird. Der beim jeweiligen Angebot angezeigte Preis wird über deine Apple-ID abgerechnet.")
                .font(.footnote)
                .foregroundStyle(.secondary)

            HStack(spacing: 18) {
                Link("Datenschutz", destination: URL(string: "https://maengelfix.kamilunavo.com/datenschutz")!)
                Link("Nutzungsbedingungen (EULA)", destination: URL(string: "https://maengelfix.kamilunavo.com/nutzungsbedingungen")!)
            }
            .font(.footnote)
        } header: {
            Text("Privat Pro")
        } footer: {
            Text("Titel, Preis und Laufzeit werden direkt aus dem App Store angezeigt. Die oben genannten Pro-Funktionen stehen für die Dauer des aktiven Abonnements zur Verfügung.")
        }
    }

'''
profile = profile[:sub_start] + new_subscription + profile[sub_end:]

# Enrich management products too, so every auto-renewable product clearly states value + term.
period_old = '''                            Text(StoreKitManager.periodLabel(for: product.id))
                                .font(.caption)
                                .foregroundStyle(.secondary)
'''
period_new = '''                            Text("\\(StoreKitManager.periodLabel(for: product.id)) · \\(managementTerm(for: product.id))")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            Text(managementBenefits(for: product.id))
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                                .multilineTextAlignment(.leading)
'''
if 'Text(managementBenefits(for: product.id))' not in profile:
    if period_old not in profile:
        raise SystemExit('Management product detail anchor not found')
    profile = profile.replace(period_old, period_new, 1)

mgmt_helper_anchor = '    private func displayDate(_ value: String) -> String {'
mgmt_helpers = '''    private func managementTerm(for productID: String) -> String {
        productID.hasSuffix(".yearly") ? "Laufzeit 1 Jahr" : "Laufzeit 1 Monat"
    }

    private func managementBenefits(for productID: String) -> String {
        switch productID {
        case StoreKitManager.managementStarterMonthlyProductID, StoreKitManager.managementStarterYearlyProductID:
            return "Bis 25 Einheiten und 3 Mitarbeiter · Mängelmanagement, Mieter, Dienstleister, Aufgaben, Kalender, Fristen und Protokolle"
        case StoreKitManager.managementProMonthlyProductID, StoreKitManager.managementProYearlyProductID:
            return "Bis 100 Einheiten und 5 Mitarbeiter · alle Starter-Funktionen plus Analysen, Qualitätsdashboard und Aktivitätsprotokoll"
        case StoreKitManager.managementBusinessMonthlyProductID, StoreKitManager.managementBusinessYearlyProductID:
            return "Bis 300 Einheiten und 10 Mitarbeiter · alle Pro-Funktionen für größere Verwaltungsbestände"
        default:
            return "MängelFix-Verwaltungsfunktionen für die gewählte Laufzeit"
        }
    }

'''
if 'private func managementBenefits(for productID:' not in profile:
    if mgmt_helper_anchor not in profile:
        raise SystemExit('Management helper anchor not found')
    profile = profile.replace(mgmt_helper_anchor, mgmt_helpers + mgmt_helper_anchor, 1)

# Add renewal + legal links to Apple management purchase area.
mgmt_end_anchor = '''        }
    }

    @ViewBuilder
    private func managementStoreProducts(user: User) -> some View {
'''
# Keep managementSubscriptionSection structure intact; legal copy is included in store products below.

products_tail = '''            ForEach(store.managementProducts, id: \.id) { product in
'''
# Add copy after the existing ForEach block by targeting the end of managementStoreProducts.
mgmt_func_start = profile.find('    @ViewBuilder\n    private func managementStoreProducts(user: User) -> some View {')
mgmt_func_end = profile.find('    private func managementTerm(for productID:', mgmt_func_start)
if mgmt_func_start == -1 or mgmt_func_end == -1:
    raise SystemExit('Management store product function boundaries not found')
mgmt_block = profile[mgmt_func_start:mgmt_func_end]
if 'Apple-Verwaltungsabos verlängern sich automatisch' not in mgmt_block:
    close_pattern = '''            }
        }
    }

'''
    insert_copy = '''            }
            Text("Apple-Verwaltungsabos verlängern sich automatisch um die gewählte Laufzeit, bis sie in den Apple-Abonnementeinstellungen gekündigt werden.")
                .font(.footnote)
                .foregroundStyle(.secondary)
            HStack(spacing: 18) {
                Link("Datenschutz", destination: URL(string: "https://maengelfix.kamilunavo.com/datenschutz")!)
                Link("Nutzungsbedingungen (EULA)", destination: URL(string: "https://maengelfix.kamilunavo.com/nutzungsbedingungen")!)
            }
            .font(.footnote)
        }
    }

'''
    idx = mgmt_block.rfind(close_pattern)
    if idx == -1:
        raise SystemExit('Management store product closing anchor not found')
    mgmt_block = mgmt_block[:idx] + insert_copy + mgmt_block[idx + len(close_pattern):]
    profile = profile[:mgmt_func_start] + mgmt_block + profile[mgmt_func_end:]

# Add dedicated native deletion flow before ProfileEditView.
delete_view_anchor = 'private struct ProfileEditView: View {'
delete_view = '''private struct AccountDeletionView: View {
    @Environment(AppSession.self) private var session
    @Environment(\\.dismiss) private var dismiss

    @State private var password = ""
    @State private var confirmation = ""
    @State private var isDeleting = false
    @State private var errorMessage: String?
    @State private var showFinalConfirmation = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text("Wenn du fortfährst, werden dein MängelFix-Konto, deine persönlichen Kontodaten und deine privaten Mängelvorgänge dauerhaft gelöscht. Dieser Schritt kann nicht rückgängig gemacht werden.")
                    Text("Falls du Inhaber einer Verwaltung bist, kann die Löschung erst erfolgen, nachdem die Inhaberschaft übertragen wurde.")
                        .foregroundStyle(.secondary)
                } header: {
                    Text("Konto dauerhaft löschen")
                }

                Section("Bestätigung") {
                    SecureField("Passwort", text: $password)
                        .textContentType(.password)
                    TextField("LÖSCHEN eingeben", text: $confirmation)
                        .textInputAutocapitalization(.characters)
                        .autocorrectionDisabled()
                }

                Section {
                    Button(role: .destructive) {
                        showFinalConfirmation = true
                    } label: {
                        HStack {
                            if isDeleting { ProgressView() }
                            Text("Konto endgültig löschen")
                        }
                    }
                    .disabled(password.isEmpty || confirmation != "LÖSCHEN" || isDeleting)
                } footer: {
                    Text("Ein über den App Store abgeschlossenes Abonnement wird durch die Kontolöschung nicht automatisch gekündigt. Verwalte es separat in deinen Apple-Abonnementeinstellungen.")
                }

                if let errorMessage {
                    Section {
                        Text(errorMessage).foregroundStyle(.red)
                    }
                }

                Section("Rechtliches") {
                    Link("Datenschutzerklärung", destination: URL(string: "https://maengelfix.kamilunavo.com/datenschutz")!)
                    Link("Nutzungsbedingungen (EULA)", destination: URL(string: "https://maengelfix.kamilunavo.com/nutzungsbedingungen")!)
                }
            }
            .navigationTitle("Konto löschen")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Abbrechen") { dismiss() }
                        .disabled(isDeleting)
                }
            }
            .confirmationDialog(
                "Konto wirklich dauerhaft löschen?",
                isPresented: $showFinalConfirmation,
                titleVisibility: .visible
            ) {
                Button("Ja, Konto dauerhaft löschen", role: .destructive) {
                    Task { await deleteAccount() }
                }
                Button("Abbrechen", role: .cancel) {}
            } message: {
                Text("Alle zu diesem Konto gehörenden persönlichen Daten und privaten Vorgänge werden gelöscht.")
            }
        }
        .interactiveDismissDisabled(isDeleting)
    }

    @MainActor
    private func deleteAccount() async {
        guard confirmation == "LÖSCHEN", !password.isEmpty else { return }
        isDeleting = true
        errorMessage = nil
        do {
            try await session.api.deleteAccount(password: password, confirmation: confirmation)
            await session.logout()
            dismiss()
        } catch {
            errorMessage = error.localizedDescription
            isDeleting = false
        }
    }
}

'''
if 'private struct AccountDeletionView:' not in profile:
    if delete_view_anchor not in profile:
        raise SystemExit('Profile edit view anchor not found')
    profile = profile.replace(delete_view_anchor, delete_view + delete_view_anchor, 1)

profile_p.write_text(profile)

# --- Build 8 for resubmission ---
project = project.replace('CURRENT_PROJECT_VERSION: 7', 'CURRENT_PROJECT_VERSION: 8')
project_p.write_text(project)

print('Prepared native iOS App Review fixes and bumped build to 8')
