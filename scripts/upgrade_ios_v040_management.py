from pathlib import Path

root = Path('.')

# ---------- Models ----------
p = root / 'ios/Sources/Core/Models.swift'
s = p.read_text()
s = s.replace('case "private_free": return "Privat Free"\n        case "management_starter"', 'case "private_free": return "Privat Free"\n        case "management_trial": return "Verwaltung · Testphase"\n        case "management_starter"', 1)
marker = 'struct UserResponse: Decodable { let user: User }'
management_models = r'''struct ManagementOrganization: Codable, Identifiable, Hashable {
    let id: String
    var name: String
    var planCode: String?
    var role: String?
    var subscriptionStatus: String?
    var trialEndsAt: String?
    var maxMembers: Int?
    var maxProperties: Int?
    var maxUnits: Int?
}

struct ManagementMetrics: Codable, Hashable {
    var properties: Int
    var units: Int
    var contacts: Int
    var open: Int
    var unassigned: Int
    var overdue: Int
}

struct ManagementRecentCase: Codable, Identifiable, Hashable {
    let id: String
    var title: String
    var status: String
    var deadlineOn: String?
    var assignedUserId: String?
    var propertyName: String?
    var unitLabel: String?
    var assignedUserName: String?

    var statusLabel: String {
        switch status {
        case "received": return "Eingegangen"
        case "reviewing": return "In Prüfung"
        case "commissioned": return "Beauftragt"
        case "scheduled": return "Terminiert"
        case "in_progress": return "In Ausführung"
        case "resolved": return "Erledigt"
        case "draft": return "Entwurf"
        case "sent": return "Versendet"
        case "reply": return "Rückmeldung"
        default: return status
        }
    }
}

struct ManagementMember: Codable, Identifiable, Hashable {
    let id: String
    var name: String
    var role: String
    var openCases: Int
}

struct ManagementOverviewResponse: Decodable {
    let organization: ManagementOrganization?
    let metrics: ManagementMetrics?
    let recent: [ManagementRecentCase]?
    let members: [ManagementMember]?
}

struct RegisterResponse: Decodable {
    let user: User
    let accountType: String?
    let organization: ManagementOrganization?
    let verificationMailSent: Bool?
}

'''
if 'struct ManagementOverviewResponse' not in s:
    if marker not in s: raise SystemExit('Models marker missing')
    s = s.replace(marker, management_models + marker, 1)
p.write_text(s)

# ---------- APIClient ----------
p = root / 'ios/Sources/Core/APIClient.swift'
s = p.read_text()
old = '''    func register(name: String, email: String, password: String) async throws -> User {
        let response: UserResponse = try await request("/api/auth/register", method: "POST", body: RegisterRequest(name: name, email: email, password: password))
        return response.user
    }
'''
new = '''    func register(name: String, email: String, password: String, accountType: String, organizationName: String?) async throws -> User {
        let response: RegisterResponse = try await request(
            "/api/auth/register",
            method: "POST",
            body: RegisterRequest(name: name, email: email, password: password, accountType: accountType, organizationName: organizationName)
        )
        return response.user
    }
'''
if old not in s: raise SystemExit('API register marker missing')
s = s.replace(old, new, 1)
anchor = '''    func cases() async throws -> [DefectCase] {
'''
addition = '''    func managementOverview() async throws -> ManagementOverviewResponse {
        try await request("/api/management/overview")
    }

'''
if 'func managementOverview()' not in s:
    if anchor not in s: raise SystemExit('API management marker missing')
    s = s.replace(anchor, addition + anchor, 1)
s = s.replace('request.setValue("MängelFix-iOS/0.3", forHTTPHeaderField: "X-MaengelFix-Client")', 'request.setValue("MängelFix-iOS/0.4", forHTTPHeaderField: "X-MaengelFix-Client")', 1)
s = s.replace('private struct RegisterRequest: Encodable { let name: String; let email: String; let password: String }', 'private struct RegisterRequest: Encodable { let name: String; let email: String; let password: String; let accountType: String; let organizationName: String? }', 1)
p.write_text(s)

# ---------- AppSession ----------
p = root / 'ios/Sources/Core/AppSession.swift'
s = p.read_text()
s = s.replace('    var user: User?\n', '''    var user: User?
    var entitlements: Entitlements?

    var isManagement: Bool {
        entitlements?.scope == "organization" || user?.onboardingUseCase == "management"
    }
''', 1)
s = s.replace('''            user = try await api.me()
            phase = .signedIn
''', '''            user = try await api.me()
            phase = .signedIn
            await refreshEntitlements()
''', 1)
s = s.replace('''    func login(email: String, password: String) async throws {
        user = try await api.login(email: email, password: password)
        phase = .signedIn
    }

    func register(name: String, email: String, password: String) async throws {
        user = try await api.register(name: name, email: email, password: password)
        phase = .signedIn
    }
''', '''    func login(email: String, password: String) async throws {
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
''', 1)
s = s.replace('''        user = nil
        phase = .signedOut
''', '''        user = nil
        entitlements = nil
        phase = .signedOut
''', 1)
p.write_text(s)

# ---------- AuthView ----------
p = root / 'ios/Sources/Features/AuthView.swift'
s = p.read_text()
rest_marker = 'private struct ForgotPasswordView: View {'
if rest_marker not in s: raise SystemExit('Auth rest marker missing')
rest = rest_marker + s.split(rest_marker, 1)[1]
auth = r'''import SwiftUI

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

'''
p.write_text(auth + rest)

# ---------- CreateCaseView ----------
p = root / 'ios/Sources/Features/CreateCaseView.swift'
s = p.read_text()
s = s.replace('''struct CreateCaseView: View {
    @Environment(AppSession.self) private var session
    let onCreated: (DefectCase) -> Void
''', '''struct CreateCaseView: View {
    @Environment(AppSession.self) private var session
    let managementMode: Bool
    let onCreated: (DefectCase) -> Void

    init(managementMode: Bool = false, onCreated: @escaping (DefectCase) -> Void) {
        self.managementMode = managementMode
        self.onCreated = onCreated
    }
''', 1)
s = s.replace('''                    Picker("Bereich", selection: $context) {
                        ForEach(contexts, id: \.0) { value, label in Text(label).tag(value) }
                    }
                    .onChange(of: context) { _, value in category = categories[value]?.first ?? "Sonstiges" }
''', '''                    if managementMode {
                        LabeledContent("Bereich", value: "Wohnen / Immobilie")
                    } else {
                        Picker("Bereich", selection: $context) {
                            ForEach(contexts, id: \.0) { value, label in Text(label).tag(value) }
                        }
                        .onChange(of: context) { _, value in category = categories[value]?.first ?? "Sonstiges" }
                    }
''', 1)
s = s.replace('''                Section("Empfänger") {
                    TextField("Name / Firma (optional)", text: $recipientName).focused($focusedField, equals: .recipientName)
                    TextField("E-Mail (optional)", text: $recipientEmail).keyboardType(.emailAddress).textInputAutocapitalization(.never).focused($focusedField, equals: .recipientEmail)
                    TextField("Anschrift (optional)", text: $recipientAddress, axis: .vertical).lineLimit(2...4).focused($focusedField, equals: .recipientAddress)
                }
''', '''                if !managementMode {
                    Section("Empfänger") {
                        TextField("Name / Firma (optional)", text: $recipientName).focused($focusedField, equals: .recipientName)
                        TextField("E-Mail (optional)", text: $recipientEmail).keyboardType(.emailAddress).textInputAutocapitalization(.never).focused($focusedField, equals: .recipientEmail)
                        TextField("Anschrift (optional)", text: $recipientAddress, axis: .vertical).lineLimit(2...4).focused($focusedField, equals: .recipientAddress)
                    }
                }
''', 1)
s = s.replace('''                    if hasDeadline { Text("Fristen sind bei Privatkonten eine Pro-Funktion.").font(.caption).foregroundStyle(.secondary) }
''', '''                    if hasDeadline {
                        Text(managementMode ? "Fristen sind während der Verwaltungs-Testphase und in aktiven Verwaltungstarifen enthalten." : "Fristen sind bei Privatkonten eine Pro-Funktion.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
''', 1)
s = s.replace('''            .navigationTitle("Neuer Mangel")
''', '''            .navigationTitle(managementMode ? "Neuer Vorgang" : "Neuer Mangel")
            .onAppear {
                if managementMode {
                    context = "housing"
                    if !(categories["housing"] ?? []).contains(category) { category = categories["housing"]?.first ?? "Sonstiges" }
                }
            }
''', 1)
s = s.replace('''                    discoveredOn: Self.apiDate.string(from: discoveredOn), recipientName: recipientName.nilIfBlank,
                    recipientEmail: recipientEmail.nilIfBlank, recipientAddress: recipientAddress.nilIfBlank,
''', '''                    discoveredOn: Self.apiDate.string(from: discoveredOn), recipientName: managementMode ? nil : recipientName.nilIfBlank,
                    recipientEmail: managementMode ? nil : recipientEmail.nilIfBlank, recipientAddress: managementMode ? nil : recipientAddress.nilIfBlank,
''', 1)
p.write_text(s)

# ---------- Management Dashboard ----------
p = root / 'ios/Sources/Features/ManagementDashboardView.swift'
p.write_text(r'''import SwiftUI

struct ManagementDashboardView: View {
    @Environment(AppSession.self) private var session
    let refreshVersion: Int

    @State private var overview: ManagementOverviewResponse?
    @State private var isLoading = true
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(spacing: 16) {
                    header
                    metricsGrid
                    recentCases
                    teamWorkload
                    if let errorMessage {
                        MFCard {
                            Label(errorMessage, systemImage: "exclamationmark.triangle")
                                .foregroundStyle(.red)
                        }
                    }
                }
                .padding()
            }
            .background(Color.mfBackground)
            .navigationTitle("Verwaltung")
            .refreshable { await reload() }
            .task(id: refreshVersion) { await reload() }
        }
    }

    private var header: some View {
        MFCard {
            VStack(alignment: .leading, spacing: 12) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("HAUSVERWALTUNG")
                            .font(.caption.bold()).tracking(1.2).foregroundStyle(.secondary)
                        Text(overview?.organization?.name ?? "MängelFix Verwaltung")
                            .font(.title2.bold())
                        Text("Hallo, \(session.user?.name ?? ""). Hier siehst du den aktuellen Stand deiner Verwaltung.")
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    if isLoading { ProgressView() }
                }

                HStack(spacing: 8) {
                    Label(planLabel, systemImage: "building.2.fill")
                        .font(.caption.bold())
                        .padding(.horizontal, 10).padding(.vertical, 6)
                        .background(Color.mfPrimary.opacity(0.1))
                        .foregroundStyle(Color.mfPrimary)
                        .clipShape(Capsule())
                    if let trialText {
                        Text(trialText)
                            .font(.caption.bold())
                            .padding(.horizontal, 10).padding(.vertical, 6)
                            .background(Color.mfAccent.opacity(0.16))
                            .clipShape(Capsule())
                    }
                }
            }
        }
    }

    private var metricsGrid: some View {
        let metrics = overview?.metrics
        return LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
            metricCard("Objekte", metrics?.properties ?? 0, "building.2")
            metricCard("Einheiten", metrics?.units ?? 0, "door.left.hand.open")
            metricCard("Offene Mängel", metrics?.open ?? 0, "exclamationmark.bubble")
            metricCard("Überfällig", metrics?.overdue ?? 0, "calendar.badge.exclamationmark")
        }
    }

    private var recentCases: some View {
        MFCard {
            VStack(alignment: .leading, spacing: 12) {
                Text("Aktuelle Vorgänge").font(.headline)
                let recent = overview?.recent ?? []
                if recent.isEmpty && !isLoading {
                    Text("Noch keine Verwaltungsvorgänge vorhanden.").foregroundStyle(.secondary)
                } else {
                    ForEach(recent) { item in
                        HStack(spacing: 10) {
                            Circle().fill(item.status == "resolved" ? Color.green : Color.mfAccent).frame(width: 8, height: 8)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(item.title).fontWeight(.semibold)
                                Text([item.propertyName, item.unitLabel, item.statusLabel].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " · "))
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                            Spacer()
                            if item.assignedUserName == nil {
                                Image(systemName: "person.crop.circle.badge.questionmark").foregroundStyle(.secondary)
                            }
                        }
                        if item.id != recent.last?.id { Divider() }
                    }
                }
            }
        }
    }

    private var teamWorkload: some View {
        MFCard {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("Team").font(.headline)
                    Spacer()
                    Text("\((overview?.members ?? []).count) Mitglieder").font(.caption).foregroundStyle(.secondary)
                }
                let members = overview?.members ?? []
                if members.isEmpty && !isLoading {
                    Text("Noch keine Teamdaten vorhanden.").foregroundStyle(.secondary)
                } else {
                    ForEach(members.prefix(5)) { member in
                        HStack {
                            Circle()
                                .fill(Color.mfPrimary.opacity(0.12))
                                .frame(width: 34, height: 34)
                                .overlay(Text(String(member.name.prefix(1)).uppercased()).font(.caption.bold()).foregroundStyle(Color.mfPrimary))
                            VStack(alignment: .leading, spacing: 2) {
                                Text(member.name).fontWeight(.semibold)
                                Text(roleLabel(member.role)).font(.caption).foregroundStyle(.secondary)
                            }
                            Spacer()
                            Text("\(member.openCases) offen").font(.caption.bold())
                        }
                    }
                }
            }
        }
    }

    private func metricCard(_ title: String, _ value: Int, _ icon: String) -> some View {
        MFCard {
            VStack(alignment: .leading, spacing: 8) {
                Image(systemName: icon).foregroundStyle(Color.mfPrimary)
                Text("\(value)").font(.title.bold())
                Text(title).font(.caption).foregroundStyle(.secondary)
            }
        }
    }

    private var planLabel: String {
        switch session.entitlements?.planCode {
        case "management_trial": return "14-Tage-Testphase"
        case "management_starter": return "Verwaltung Starter"
        case "management_pro": return "Verwaltung Pro"
        case "management_business": return "Verwaltung Business"
        default: return "Verwaltung"
        }
    }

    private var trialText: String? {
        guard session.entitlements?.status == "trialing", let value = session.entitlements?.trialEndsAt, let end = parseISODate(value) else { return nil }
        let days = max(0, Calendar.current.dateComponents([.day], from: Calendar.current.startOfDay(for: Date()), to: Calendar.current.startOfDay(for: end)).day ?? 0)
        return days == 1 ? "noch 1 Tag" : "noch \(days) Tage"
    }

    private func roleLabel(_ role: String) -> String {
        switch role { case "owner": return "Inhaber"; case "admin": return "Admin"; default: return "Mitarbeiter" }
    }

    private func parseISODate(_ value: String) -> Date? {
        let fractional = ISO8601DateFormatter(); fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = fractional.date(from: value) { return date }
        return ISO8601DateFormatter().date(from: value)
    }

    @MainActor
    private func reload() async {
        isLoading = true
        errorMessage = nil
        do {
            overview = try await session.api.managementOverview()
            await session.refreshEntitlements()
            await session.refreshUser()
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}
''')

# ---------- Main app shell ----------
p = root / 'ios/Sources/MaengelFixApp.swift'
s = p.read_text()
s = s.replace('''            if session.phase == .signedIn {
                await store.loadProducts()
            }
''', '''            if session.phase == .signedIn && !session.isManagement {
                await store.loadProducts()
            }
''', 1)
s = s.replace('''private struct MainTabView: View {
    @State private var selectedTab: AppTab = .dashboard
''', '''private struct MainTabView: View {
    @Environment(AppSession.self) private var session
    @State private var selectedTab: AppTab = .dashboard
''', 1)
s = s.replace('''            DashboardView(refreshVersion: caseRefreshVersion)
                .tabItem { Label("Übersicht", systemImage: "square.grid.2x2") }
                .tag(AppTab.dashboard)

            CasesView(refreshVersion: caseRefreshVersion)
                .tabItem { Label("Mängel", systemImage: "exclamationmark.bubble") }
                .tag(AppTab.cases)

            CreateCaseView { _ in
''', '''            Group {
                if session.isManagement {
                    ManagementDashboardView(refreshVersion: caseRefreshVersion)
                } else {
                    DashboardView(refreshVersion: caseRefreshVersion)
                }
            }
            .tabItem { Label(session.isManagement ? "Verwaltung" : "Übersicht", systemImage: session.isManagement ? "building.2" : "square.grid.2x2") }
            .tag(AppTab.dashboard)

            CasesView(refreshVersion: caseRefreshVersion)
                .tabItem { Label(session.isManagement ? "Vorgänge" : "Mängel", systemImage: "exclamationmark.bubble") }
                .tag(AppTab.cases)

            CreateCaseView(managementMode: session.isManagement) { _ in
''', 1)
p.write_text(s)

# ---------- Profile ----------
p = root / 'ios/Sources/Features/ProfileView.swift'
s = p.read_text()
s = s.replace('''                    Section("Konto") {
                        LabeledContent("Tarif", value: user.planLabel)
''', '''                    Section("Konto") {
                        LabeledContent("Kontotyp", value: session.isManagement ? "Hausverwaltung" : "Privat")
                        LabeledContent("Tarif", value: session.isManagement ? managementPlanLabel : user.planLabel)
''', 1)
s = s.replace('''                    subscriptionSection(user: user)
''', '''                    if session.isManagement {
                        managementSubscriptionSection
                    } else {
                        subscriptionSection(user: user)
                    }
''', 1)
s = s.replace('''                LabeledContent("App-Version", value: "0.3.0")
''', '''                LabeledContent("App-Version", value: "0.4.0")
''', 1)
s = s.replace('''            .task {
                await session.refreshUser()
                await store.loadProducts()
            }
''', '''            .task {
                await session.refreshUser()
                await session.refreshEntitlements()
                if !session.isManagement { await store.loadProducts() }
            }
''', 1)
anchor = '''    @ViewBuilder
    private func subscriptionSection(user: User) -> some View {
'''
management_section = r'''    private var managementPlanLabel: String {
        switch session.entitlements?.planCode {
        case "management_trial": return "Verwaltung · Testphase"
        case "management_starter": return "Verwaltung Starter"
        case "management_pro": return "Verwaltung Pro"
        case "management_business": return "Verwaltung Business"
        default: return "Verwaltung"
        }
    }

    @ViewBuilder
    private var managementSubscriptionSection: some View {
        Section("Verwaltung") {
            if let entitlements = session.entitlements {
                Label(entitlements.pro ? "Verwaltungsfunktionen sind aktiv" : "Verwaltungstarif ist nicht aktiv", systemImage: entitlements.pro ? "checkmark.seal.fill" : "exclamationmark.triangle.fill")
                    .foregroundStyle(entitlements.pro ? Color.mfPrimary : Color.orange)
                if entitlements.status == "trialing" {
                    LabeledContent("Testphase", value: "14 Tage kostenlos")
                    if let end = entitlements.trialEndsAt { LabeledContent("Test endet", value: displayDate(end)) }
                }
                if let used = entitlements.usage.members, let limit = entitlements.limits.members { LabeledContent("Team", value: "\(used) / \(limit)") }
                if let used = entitlements.usage.properties, let limit = entitlements.limits.properties { LabeledContent("Objekte", value: "\(used) / \(limit)") }
                if let used = entitlements.usage.units, let limit = entitlements.limits.units { LabeledContent("Einheiten", value: "\(used) / \(limit)") }
            } else {
                HStack { ProgressView(); Text("Verwaltungsstatus wird geladen …") }
            }
            Text("Privat-Pro-Abos aus dem App Store werden für Verwaltungskonten nicht angeboten.")
                .font(.footnote).foregroundStyle(.secondary)
        }
    }

    private func displayDate(_ value: String) -> String {
        let fractional = ISO8601DateFormatter(); fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let date = fractional.date(from: value) ?? ISO8601DateFormatter().date(from: value)
        guard let date else { return value }
        return date.formatted(date: .abbreviated, time: .omitted)
    }

'''
if management_section not in s:
    if anchor not in s: raise SystemExit('Profile marker missing')
    s = s.replace(anchor, management_section + anchor, 1)
p.write_text(s)

# ---------- Version ----------
p = root / 'ios/project.yml'
s = p.read_text().replace('CURRENT_PROJECT_VERSION: 3', 'CURRENT_PROJECT_VERSION: 4', 1).replace('MARKETING_VERSION: 0.3.0', 'MARKETING_VERSION: 0.4.0', 1)
p.write_text(s)

print('iOS v0.4 management account upgrade prepared')
