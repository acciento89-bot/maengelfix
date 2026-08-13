import SwiftUI

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
