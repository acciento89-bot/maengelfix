import SwiftUI

struct DashboardView: View {
    @Environment(AppSession.self) private var session
    let refreshVersion: Int

    @State private var cases: [DefectCase] = []
    @State private var entitlements: Entitlements?
    @State private var isLoading = true
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(spacing: 16) {
                    header
                    stats

                    if let errorMessage {
                        MFCard {
                            Label(errorMessage, systemImage: "exclamationmark.triangle")
                                .foregroundStyle(.red)
                        }
                    }

                    MFCard {
                        VStack(alignment: .leading, spacing: 12) {
                            HStack {
                                Text("Zuletzt aktualisiert")
                                    .font(.headline)
                                Spacer()
                                if isLoading { ProgressView() }
                            }

                            if cases.isEmpty && !isLoading {
                                ContentUnavailableView(
                                    "Noch keine Vorgänge",
                                    systemImage: "checklist",
                                    description: Text("Lege deinen ersten Mangel über den Tab „Neu“ an.")
                                )
                            } else {
                                ForEach(cases.prefix(5)) { item in
                                    HStack(spacing: 12) {
                                        Circle()
                                            .fill(item.status == "resolved" ? Color.green : Color.mfAccent)
                                            .frame(width: 8, height: 8)
                                        VStack(alignment: .leading, spacing: 3) {
                                            Text(item.title).fontWeight(.semibold)
                                            Text(item.statusLabel)
                                                .font(.caption)
                                                .foregroundStyle(.secondary)
                                        }
                                        Spacer()
                                        if let count = item.attachmentCount, count > 0 {
                                            Label("\(count)", systemImage: "paperclip")
                                                .font(.caption)
                                                .foregroundStyle(.secondary)
                                        }
                                    }
                                    if item.id != cases.prefix(5).last?.id { Divider() }
                                }
                            }
                        }
                    }
                }
                .padding()
            }
            .background(Color.mfBackground)
            .navigationTitle("Übersicht")
            .refreshable { await reload() }
            .task(id: refreshVersion) { await reload() }
        }
    }

    private var header: some View {
        MFCard {
            HStack(alignment: .top, spacing: 14) {
                MFLogo(compact: true)
                VStack(alignment: .leading, spacing: 5) {
                    Text("Hallo, \(session.user?.name ?? "")")
                        .font(.title2.bold())
                    Text(entitlements?.pro == true ? "Pro-Funktionen sind aktiv." : "Dein MängelFix Konto ist bereit.")
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Text(session.user?.planLabel ?? "")
                    .font(.caption.bold())
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(Color.mfPrimary.opacity(0.1))
                    .foregroundStyle(Color.mfPrimary)
                    .clipShape(Capsule())
            }
        }
    }

    private var stats: some View {
        let open = cases.filter { $0.status != "resolved" && $0.archivedAt == nil }.count
        let resolved = cases.filter { $0.status == "resolved" }.count
        let deadlines = cases.filter { ($0.deadlineOn?.isEmpty == false) && $0.status != "resolved" }.count

        return HStack(spacing: 10) {
            statCard("Offen", value: open, icon: "exclamationmark.circle")
            statCard("Erledigt", value: resolved, icon: "checkmark.circle")
            statCard("Fristen", value: deadlines, icon: "calendar.badge.clock")
        }
    }

    private func statCard(_ title: String, value: Int, icon: String) -> some View {
        MFCard {
            VStack(alignment: .leading, spacing: 8) {
                Image(systemName: icon)
                    .foregroundStyle(Color.mfPrimary)
                Text("\(value)")
                    .font(.title.bold())
                Text(title)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }

    @MainActor
    private func reload() async {
        isLoading = true
        errorMessage = nil
        do {
            async let loadedCases = session.api.cases()
            async let loadedEntitlements = session.api.entitlements()
            cases = try await loadedCases
            entitlements = try await loadedEntitlements
            await session.refreshUser()
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}
