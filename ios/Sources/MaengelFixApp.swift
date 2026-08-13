import SwiftUI

@main
struct MaengelFixApp: App {
    @State private var session = AppSession()
    @State private var store = StoreKitManager()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(session)
                .environment(store)
                .tint(.mfPrimary)
        }
    }
}

private struct RootView: View {
    @Environment(AppSession.self) private var session
    @Environment(StoreKitManager.self) private var store

    var body: some View {
        Group {
            switch session.phase {
            case .loading:
                VStack(spacing: 22) {
                    MFLogo()
                    ProgressView("MängelFix wird geladen …")
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color.mfBackground)

            case .signedOut:
                AuthView()

            case .signedIn:
                MainTabView()
            }
        }
        .task {
            await session.restoreIfNeeded()
            if session.phase == .signedIn {
                await store.loadProducts()
            }
        }
    }
}

private enum AppTab: Hashable {
    case dashboard
    case cases
    case create
    case profile
}

private struct MainTabView: View {
    @State private var selectedTab: AppTab = .dashboard
    @State private var caseRefreshVersion = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            DashboardView(refreshVersion: caseRefreshVersion)
                .tabItem { Label("Übersicht", systemImage: "square.grid.2x2") }
                .tag(AppTab.dashboard)

            CasesView(refreshVersion: caseRefreshVersion)
                .tabItem { Label("Mängel", systemImage: "exclamationmark.bubble") }
                .tag(AppTab.cases)

            CreateCaseView { _ in
                caseRefreshVersion += 1
                selectedTab = .cases
            }
            .tabItem { Label("Neu", systemImage: "plus.circle.fill") }
            .tag(AppTab.create)

            ProfileView()
                .tabItem { Label("Profil", systemImage: "person.crop.circle") }
                .tag(AppTab.profile)
        }
    }
}
