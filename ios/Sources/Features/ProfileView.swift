import SwiftUI

struct ProfileView: View {
    @Environment(AppSession.self) private var session
    @State private var isLoggingOut = false

    var body: some View {
        NavigationStack {
            List {
                if let user = session.user {
                    Section {
                        HStack(spacing: 14) {
                            ZStack {
                                Circle().fill(Color.mfPrimary.opacity(0.12))
                                Text(initials(user.name))
                                    .font(.title3.bold())
                                    .foregroundStyle(Color.mfPrimary)
                            }
                            .frame(width: 52, height: 52)

                            VStack(alignment: .leading, spacing: 3) {
                                Text(user.name).font(.headline)
                                Text(user.email)
                                    .font(.subheadline)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }

                    Section("Konto") {
                        LabeledContent("Tarif", value: user.planLabel)
                        LabeledContent("E-Mail bestätigt", value: user.emailVerified ? "Ja" : "Nein")
                        if !user.city.isEmpty {
                            LabeledContent("Ort", value: [user.postalCode, user.city].filter { !$0.isEmpty }.joined(separator: " "))
                        }
                    }
                }

                Section("MängelFix") {
                    LabeledContent("App-Version", value: "0.1.0")
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
            .task { await session.refreshUser() }
        }
    }

    private func initials(_ name: String) -> String {
        name.split(separator: " ")
            .prefix(2)
            .compactMap(\.first)
            .map(String.init)
            .joined()
            .uppercased()
    }
}
