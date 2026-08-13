import SwiftUI

struct CasesView: View {
    @Environment(AppSession.self) private var session
    let refreshVersion: Int

    @State private var cases: [DefectCase] = []
    @State private var searchText = ""
    @State private var isLoading = true
    @State private var errorMessage: String?

    private var filteredCases: [DefectCase] {
        guard !searchText.isEmpty else { return cases }
        return cases.filter {
            $0.title.localizedCaseInsensitiveContains(searchText) ||
            ($0.propertyLabel?.localizedCaseInsensitiveContains(searchText) ?? false) ||
            ($0.category?.localizedCaseInsensitiveContains(searchText) ?? false)
        }
    }

    var body: some View {
        NavigationStack {
            Group {
                if isLoading && cases.isEmpty {
                    ProgressView("Vorgänge werden geladen …")
                } else if let errorMessage, cases.isEmpty {
                    ContentUnavailableView(
                        "Vorgänge konnten nicht geladen werden",
                        systemImage: "wifi.exclamationmark",
                        description: Text(errorMessage)
                    )
                } else if filteredCases.isEmpty {
                    ContentUnavailableView.search(text: searchText)
                } else {
                    List(filteredCases) { item in
                        NavigationLink(value: item.id) {
                            CaseRow(item: item)
                        }
                    }
                    .listStyle(.insetGrouped)
                }
            }
            .navigationTitle("Mängel")
            .searchable(text: $searchText, prompt: "Titel, Objekt oder Kategorie")
            .navigationDestination(for: String.self) { caseID in
                CaseDetailView(caseID: caseID)
            }
            .refreshable { await reload() }
            .task(id: refreshVersion) { await reload() }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        Task { await reload() }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                }
            }
        }
    }

    @MainActor
    private func reload() async {
        isLoading = true
        errorMessage = nil
        do {
            cases = try await session.api.cases()
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

private struct CaseRow: View {
    let item: DefectCase

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            RoundedRectangle(cornerRadius: 3)
                .fill(item.status == "resolved" ? Color.green : Color.mfAccent)
                .frame(width: 5)

            VStack(alignment: .leading, spacing: 5) {
                Text(item.title)
                    .font(.headline)
                HStack(spacing: 8) {
                    Text(item.statusLabel)
                    if let category = item.category, !category.isEmpty {
                        Text("·")
                        Text(category)
                    }
                }
                .font(.caption)
                .foregroundStyle(.secondary)

                if let property = item.propertyLabel, !property.isEmpty {
                    Label(property, systemImage: "building.2")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()

            if let count = item.attachmentCount, count > 0 {
                Label("\(count)", systemImage: "paperclip")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 4)
    }
}

private struct CaseDetailView: View {
    @Environment(AppSession.self) private var session
    let caseID: String

    @State private var detail: CaseDetailResponse?
    @State private var isLoading = true
    @State private var errorMessage: String?

    var body: some View {
        ScrollView {
            if isLoading && detail == nil {
                ProgressView("Vorgang wird geladen …")
                    .padding(.top, 60)
            } else if let errorMessage, detail == nil {
                ContentUnavailableView(
                    "Vorgang konnte nicht geladen werden",
                    systemImage: "exclamationmark.triangle",
                    description: Text(errorMessage)
                )
            } else if let detail {
                LazyVStack(spacing: 16) {
                    MFCard {
                        VStack(alignment: .leading, spacing: 12) {
                            HStack {
                                Text(detail.caseItem.statusLabel)
                                    .font(.caption.bold())
                                    .padding(.horizontal, 9)
                                    .padding(.vertical, 5)
                                    .background(Color.mfPrimary.opacity(0.1))
                                    .foregroundStyle(Color.mfPrimary)
                                    .clipShape(Capsule())
                                Spacer()
                                if let category = detail.caseItem.category {
                                    Text(category)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }

                            Text(detail.caseItem.title)
                                .font(.title2.bold())

                            if let description = detail.caseItem.description, !description.isEmpty {
                                Text(description)
                                    .foregroundStyle(.secondary)
                            }

                            if let property = detail.caseItem.propertyLabel, !property.isEmpty {
                                Label(property, systemImage: "building.2")
                            }
                            if let location = detail.caseItem.locationLabel, !location.isEmpty {
                                Label(location, systemImage: "mappin.and.ellipse")
                            }
                            if let deadline = detail.caseItem.deadlineOn, !deadline.isEmpty {
                                Label(deadline, systemImage: "calendar.badge.clock")
                            }
                        }
                    }

                    MFCard {
                        VStack(alignment: .leading, spacing: 12) {
                            Label("Nachweise", systemImage: "paperclip")
                                .font(.headline)
                            if detail.attachments.isEmpty {
                                Text("Noch keine Fotos oder Dokumente vorhanden.")
                                    .foregroundStyle(.secondary)
                            } else {
                                ForEach(detail.attachments) { attachment in
                                    HStack {
                                        Image(systemName: attachment.mimeType == "application/pdf" ? "doc.fill" : "photo")
                                            .foregroundStyle(Color.mfPrimary)
                                        Text(attachment.originalName)
                                            .lineLimit(1)
                                        Spacer()
                                    }
                                    if attachment.id != detail.attachments.last?.id { Divider() }
                                }
                            }
                        }
                    }

                    MFCard {
                        VStack(alignment: .leading, spacing: 12) {
                            Label("Verlauf", systemImage: "clock.arrow.circlepath")
                                .font(.headline)
                            if detail.events.isEmpty {
                                Text("Noch keine Verlaufseinträge.")
                                    .foregroundStyle(.secondary)
                            } else {
                                ForEach(detail.events.prefix(12)) { event in
                                    VStack(alignment: .leading, spacing: 3) {
                                        Text(event.note ?? event.eventType ?? "Aktualisierung")
                                            .font(.subheadline)
                                        if let actor = event.actorName {
                                            Text(actor)
                                                .font(.caption)
                                                .foregroundStyle(.secondary)
                                        }
                                    }
                                    if event.id != detail.events.prefix(12).last?.id { Divider() }
                                }
                            }
                        }
                    }
                }
                .padding()
            }
        }
        .background(Color.mfBackground)
        .navigationTitle("Vorgang")
        .navigationBarTitleDisplayMode(.inline)
        .refreshable { await reload() }
        .task { await reload() }
    }

    @MainActor
    private func reload() async {
        isLoading = true
        errorMessage = nil
        do {
            detail = try await session.api.caseDetail(id: caseID)
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}
