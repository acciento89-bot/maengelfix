import StoreKit
import SwiftUI

struct ProfileView: View {
    @Environment(AppSession.self) private var session
    @Environment(StoreKitManager.self) private var store
    @Environment(\.openURL) private var openURL
    @State private var isLoggingOut = false
    @State private var showEdit = false
    @State private var verificationMessage: String?
    @State private var billingMessage: String?
    @State private var showDeleteAccount = false

    var body: some View {
        NavigationStack {
            List {
                if let user = session.user {
                    Section {
                        HStack(spacing: 14) {
                            ZStack {
                                Circle().fill(Color.mfPrimary.opacity(0.12))
                                Text(initials(user.name)).font(.title3.bold()).foregroundStyle(Color.mfPrimary)
                            }
                            .frame(width: 52, height: 52)

                            VStack(alignment: .leading, spacing: 3) {
                                Text(user.name).font(.headline)
                                Text(user.email).font(.subheadline).foregroundStyle(.secondary)
                            }
                            Spacer()
                            Button("Bearbeiten") { showEdit = true }
                        }
                    }

                    Section("Konto") {
                        LabeledContent("Kontotyp", value: session.isManagement ? "Hausverwaltung" : "Privat")
                        LabeledContent("Tarif", value: session.isManagement ? managementPlanLabel : user.planLabel)
                        LabeledContent("E-Mail bestätigt", value: user.emailVerified ? "Ja" : "Nein")
                        if !user.city.isEmpty {
                            LabeledContent("Ort", value: [user.postalCode, user.city].filter { !$0.isEmpty }.joined(separator: " "))
                        }
                        if !user.emailVerified {
                            Button("Bestätigungs-E-Mail erneut senden") { Task { await resendVerification() } }
                        }
                        if let verificationMessage {
                            Text(verificationMessage).font(.caption).foregroundStyle(.secondary)
                        }
                    }

                    if session.isManagement {
                        managementSubscriptionSection(user: user)
                    } else {
                        subscriptionSection(user: user)
                    }

                    accountPrivacySection
                }

                Section("MängelFix") {
                    LabeledContent("App-Version", value: appVersionLabel)
                    LabeledContent("Backend", value: "maengelfix.kamilunavo.com")
                }

                Section {
                    Button(role: .destructive) {
                        Task {
                            isLoggingOut = true
                            await session.logout()
                            isLoggingOut = false
                        }
                    } label: {
                        HStack {
                            if isLoggingOut { ProgressView() }
                            Text("Abmelden")
                        }
                    }
                    .disabled(isLoggingOut)
                }
            }
            .navigationTitle("Profil")
            .task {
                await session.refreshUser()
                await session.refreshEntitlements()
                await store.loadProducts()
                if let id = session.user?.id, let token = UUID(uuidString: id) {
                    await store.refreshLocalEntitlements(accountToken: token)
                }
            }
            .sheet(isPresented: $showEdit) {
                if let user = session.user {
                    NavigationStack {
                        ProfileEditView(user: user) { updated in
                            session.user = updated
                            showEdit = false
                        }
                    }
                }
            }
            .sheet(isPresented: $showDeleteAccount) {
                AccountDeletionView()
            }
        }
    }

    @ViewBuilder
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

    private var appVersionLabel: String {
        let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "0.4.0"
        let build = Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "?"
        return "\(version) (\(build))"
    }

    private var managementPlanLabel: String {
        switch session.entitlements?.planCode {
        case "management_trial": return "Verwaltung · Testphase"
        case "management_starter": return "Verwaltung Starter"
        case "management_pro": return "Verwaltung Pro"
        case "management_business": return "Verwaltung Business"
        default: return "Verwaltung"
        }
    }

    private var canManageManagementBilling: Bool {
        guard let role = session.entitlements?.role else { return false }
        return role == "owner" || role == "admin"
    }

    @ViewBuilder
    private func managementSubscriptionSection(user: User) -> some View {
        Section("Verwaltung") {
            if let entitlements = session.entitlements {
                Label(
                    entitlements.pro ? "Verwaltungsfunktionen sind aktiv" : "Verwaltungstarif ist nicht aktiv",
                    systemImage: entitlements.pro ? "checkmark.seal.fill" : "exclamationmark.triangle.fill"
                )
                .foregroundStyle(entitlements.pro ? Color.mfPrimary : Color.orange)

                if entitlements.status == "trialing" {
                    LabeledContent("Testphase", value: "14 Tage kostenlos")
                    if let end = entitlements.trialEndsAt {
                        LabeledContent("Test endet", value: displayDate(end))
                    }
                }
                if let used = entitlements.usage.members, let limit = entitlements.limits.members {
                    LabeledContent("Team", value: "\(used) / \(limit)")
                }
                if let used = entitlements.usage.properties, let limit = entitlements.limits.properties {
                    LabeledContent("Objekte", value: "\(used) / \(limit)")
                }
                if let used = entitlements.usage.units, let limit = entitlements.limits.units {
                    LabeledContent("Einheiten", value: "\(used) / \(limit)")
                }

                if canManageManagementBilling {
                    if entitlements.provider == "stripe" {
                        Text("Dieser Verwaltungstarif wird über die MängelFix-Webseite abgerechnet. Änderungen erfolgen dort, damit kein zweites Abo entsteht.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    } else {
                        managementStoreProducts(user: user)

                        Button("Käufe wiederherstellen") {
                            Task { await restorePurchases(user: user) }
                        }
                        .disabled(store.isPurchasing)

                        if entitlements.provider == "apple" && entitlements.status == "active" {
                            Button("App-Store-Abo verwalten") {
                                if let url = URL(string: "https://apps.apple.com/account/subscriptions") { openURL(url) }
                            }
                        }
                    }
                } else {
                    Text("Nur Inhaber und Administratoren können den Verwaltungstarif ändern.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            } else {
                HStack { ProgressView(); Text("Verwaltungsstatus wird geladen …") }
            }

            if store.isPurchasing {
                HStack { ProgressView(); Text("App Store wird verarbeitet …") }
            }
            if let billingMessage {
                Text(billingMessage).font(.footnote).foregroundStyle(.secondary)
            }
        }
    }

    @ViewBuilder
    private func managementStoreProducts(user: User) -> some View {
        if store.isLoading {
            HStack { ProgressView(); Text("App-Store-Angebote werden geladen …") }
        } else if store.managementProducts.isEmpty {
            Text("Die Verwaltungs-Abos sind im App Store noch nicht verfügbar. Bitte prüfe die Produkte in App Store Connect.")
                .font(.footnote)
                .foregroundStyle(.secondary)
        } else {
            ForEach(store.managementProducts, id: \.id) { product in
                let active = store.isProductActive(product.id)
                Button {
                    Task { await buy(product, user: user) }
                } label: {
                    HStack(spacing: 12) {
                        VStack(alignment: .leading, spacing: 3) {
                            Text(StoreKitManager.managementTitle(for: product.id))
                                .foregroundStyle(.primary)
                            Text("\(StoreKitManager.periodLabel(for: product.id)) · \(managementTerm(for: product.id))")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            Text(managementBenefits(for: product.id))
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                                .multilineTextAlignment(.leading)
                        }
                        Spacer()
                        if active {
                            Label("Aktiv", systemImage: "checkmark.circle.fill")
                                .font(.caption)
                                .foregroundStyle(Color.mfPrimary)
                        } else {
                            Text(product.displayPrice).fontWeight(.semibold)
                        }
                    }
                }
                .disabled(store.isPurchasing || active)
            }
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

    private func managementTerm(for productID: String) -> String {
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

    private func displayDate(_ value: String) -> String {
        let fractional = ISO8601DateFormatter(); fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let date = fractional.date(from: value) ?? ISO8601DateFormatter().date(from: value)
        guard let date else { return value }
        return date.formatted(date: .abbreviated, time: .omitted)
    }

    @ViewBuilder
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

    @MainActor private func buy(_ product: Product, user: User) async {
        billingMessage = nil
        do {
            if try await store.purchase(product, userID: user.id, api: session.api) {
                await session.refreshUser()
                await session.refreshEntitlements()
                billingMessage = session.isManagement ? "Der Verwaltungstarif ist jetzt aktiv." : "Privat Pro ist jetzt aktiv."
            }
        } catch {
            billingMessage = error.localizedDescription
        }
    }

    @MainActor private func restorePurchases(user: User) async {
        billingMessage = nil
        do {
            let restored = try await store.restore(userID: user.id, api: session.api)
            await session.refreshUser()
            await session.refreshEntitlements()
            billingMessage = restored ? "Käufe wurden wiederhergestellt." : "Für dieses Apple-Konto wurde kein aktives MängelFix-Abo für dieses Konto gefunden."
        } catch {
            billingMessage = error.localizedDescription
        }
    }

    @MainActor private func resendVerification() async {
        do {
            let response = try await session.api.resendVerification()
            verificationMessage = response.alreadyVerified == true ? "E-Mail ist bereits bestätigt." : "Bestätigungs-E-Mail wurde versendet."
        } catch {
            verificationMessage = error.localizedDescription
        }
    }

    private func initials(_ name: String) -> String {
        name.split(separator: " ").prefix(2).compactMap(\.first).map(String.init).joined().uppercased()
    }
}

private struct AccountDeletionView: View {
    @Environment(AppSession.self) private var session
    @Environment(\.dismiss) private var dismiss

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

private struct ProfileEditView: View {
    @Environment(AppSession.self) private var session
    @Environment(\.dismiss) private var dismiss
    let user: User
    let onSaved: (User) -> Void

    @State private var name: String
    @State private var street: String
    @State private var postalCode: String
    @State private var city: String
    @State private var country: String
    @State private var phone: String
    @State private var isSaving = false
    @State private var errorMessage: String?

    init(user: User, onSaved: @escaping (User) -> Void) {
        self.user = user
        self.onSaved = onSaved
        _name = State(initialValue: user.name)
        _street = State(initialValue: user.street)
        _postalCode = State(initialValue: user.postalCode)
        _city = State(initialValue: user.city)
        _country = State(initialValue: user.country)
        _phone = State(initialValue: user.phone)
    }

    var body: some View {
        Form {
            Section("Persönliche Daten") {
                TextField("Name", text: $name)
                TextField("Straße", text: $street)
                TextField("PLZ", text: $postalCode)
                TextField("Ort", text: $city)
                TextField("Land", text: $country)
                TextField("Telefon", text: $phone).keyboardType(.phonePad)
            }
            if let errorMessage { Section { Text(errorMessage).foregroundStyle(.red) } }
        }
        .navigationTitle("Profil bearbeiten")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .cancellationAction) { Button("Abbrechen") { dismiss() } }
            ToolbarItem(placement: .confirmationAction) {
                Button("Speichern") { Task { await save() } }.disabled(name.trimmed.isEmpty || isSaving)
            }
        }
    }

    @MainActor private func save() async {
        isSaving = true
        errorMessage = nil
        do {
            let updated = try await session.api.updateProfile(UpdateProfileRequest(
                name: name.trimmed, street: street.trimmed, postalCode: postalCode.trimmed,
                city: city.trimmed, country: country.trimmed, phone: phone.trimmed
            ))
            onSaved(updated)
        } catch {
            errorMessage = error.localizedDescription
        }
        isSaving = false
    }
}
