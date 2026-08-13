import SwiftUI
import PhotosUI
import UIKit
import QuickLook

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
                    ContentUnavailableView("Vorgänge konnten nicht geladen werden", systemImage: "wifi.exclamationmark", description: Text(errorMessage))
                } else if filteredCases.isEmpty {
                    ContentUnavailableView.search(text: searchText)
                } else {
                    List(filteredCases) { item in
                        NavigationLink(value: item.id) { CaseRow(item: item) }
                    }
                    .listStyle(.insetGrouped)
                }
            }
            .navigationTitle("Mängel")
            .searchable(text: $searchText, prompt: "Titel, Objekt oder Kategorie")
            .navigationDestination(for: String.self) { CaseDetailView(caseID: $0) }
            .refreshable { await reload() }
            .task(id: refreshVersion) { await reload() }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { Task { await reload() } } label: { Image(systemName: "arrow.clockwise") }
                }
            }
        }
    }

    @MainActor private func reload() async {
        isLoading = true; errorMessage = nil
        do { cases = try await session.api.cases() } catch { errorMessage = error.localizedDescription }
        isLoading = false
    }
}

private struct CaseRow: View {
    let item: DefectCase
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            RoundedRectangle(cornerRadius: 3).fill(item.status == "resolved" ? Color.green : Color.mfAccent).frame(width: 5)
            VStack(alignment: .leading, spacing: 5) {
                Text(item.title).font(.headline)
                HStack(spacing: 8) {
                    Text(item.statusLabel)
                    if let category = item.category, !category.isEmpty { Text("·"); Text(category) }
                }.font(.caption).foregroundStyle(.secondary)
                if let property = item.propertyLabel, !property.isEmpty {
                    Label(property, systemImage: "building.2").font(.caption).foregroundStyle(.secondary)
                }
            }
            Spacer()
            if let count = item.attachmentCount, count > 0 {
                Label("\(count)", systemImage: "paperclip").font(.caption).foregroundStyle(.secondary)
            }
        }.padding(.vertical, 4)
    }
}

private struct CaseDetailView: View {
    @Environment(AppSession.self) private var session
    let caseID: String

    @State private var detail: CaseDetailResponse?
    @State private var isLoading = true
    @State private var errorMessage: String?
    @State private var showEdit = false
    @State private var showCamera = false
    @State private var selectedPhotos: [PhotosPickerItem] = []
    @State private var isUploading = false
    @State private var messageText = ""
    @State private var isSendingMessage = false
    @State private var pdfItem: PDFItem?
    @State private var isPreparingPDF = false

    var body: some View {
        ScrollView {
            if isLoading && detail == nil {
                ProgressView("Vorgang wird geladen …").padding(.top, 60)
            } else if let errorMessage, detail == nil {
                ContentUnavailableView("Vorgang konnte nicht geladen werden", systemImage: "exclamationmark.triangle", description: Text(errorMessage))
            } else if let detail {
                LazyVStack(spacing: 16) {
                    summaryCard(detail)
                    evidenceCard(detail)
                    if detail.caseItem.submittedByTenant == true { messagesCard(detail) }
                    historyCard(detail)
                }.padding()
            }
        }
        .background(Color.mfBackground)
        .navigationTitle("Vorgang")
        .navigationBarTitleDisplayMode(.inline)
        .refreshable { await reload() }
        .task { await reload() }
        .onChange(of: selectedPhotos) { _, items in Task { await uploadSelected(items) } }
        .sheet(isPresented: $showCamera) {
            CameraPicker { image in
                guard let draft = draftImage(from: image) else { return }
                Task { await upload([draft.uploadFile]) }
            }.ignoresSafeArea()
        }
        .sheet(isPresented: $showEdit) {
            if let item = detail?.caseItem {
                NavigationStack {
                    CaseEditView(item: item) { updated in
                        if let old = detail {
                            detail = CaseDetailResponse(caseItem: updated, events: old.events, attachments: old.attachments, messages: old.messages, viewerRole: old.viewerRole)
                        }
                        showEdit = false
                    }
                }
            }
        }
        .sheet(item: $pdfItem) { item in PDFPreview(url: item.url) }
        .toolbar {
            ToolbarItemGroup(placement: .topBarTrailing) {
                Button { Task { await preparePDF() } } label: {
                    if isPreparingPDF { ProgressView() } else { Image(systemName: "doc.richtext") }
                }
                Button("Bearbeiten") { showEdit = true }.disabled(detail == nil)
            }
        }
    }

    private func summaryCard(_ detail: CaseDetailResponse) -> some View {
        MFCard {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text(detail.caseItem.statusLabel)
                        .font(.caption.bold()).padding(.horizontal, 9).padding(.vertical, 5)
                        .background(Color.mfPrimary.opacity(0.1)).foregroundStyle(Color.mfPrimary).clipShape(Capsule())
                    Spacer()
                    if let category = detail.caseItem.category { Text(category).font(.caption).foregroundStyle(.secondary) }
                }
                Text(detail.caseItem.title).font(.title2.bold())
                if let description = detail.caseItem.description, !description.isEmpty { Text(description).foregroundStyle(.secondary) }
                if let property = detail.caseItem.propertyLabel, !property.isEmpty { Label(property, systemImage: "building.2") }
                if let location = detail.caseItem.locationLabel, !location.isEmpty { Label(location, systemImage: "mappin.and.ellipse") }
                if let discovered = detail.caseItem.discoveredOn, !discovered.isEmpty { Label("Festgestellt: \(displayDate(discovered))", systemImage: "calendar") }
                if let deadline = detail.caseItem.deadlineOn, !deadline.isEmpty { Label("Frist: \(displayDate(deadline))", systemImage: "calendar.badge.clock") }
                if let recipient = detail.caseItem.recipientName, !recipient.isEmpty { Label(recipient, systemImage: "person.text.rectangle") }
            }
        }
    }

    private func evidenceCard(_ detail: CaseDetailResponse) -> some View {
        MFCard {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Label("Nachweise", systemImage: "paperclip").font(.headline)
                    Spacer()
                    if isUploading { ProgressView() }
                }
                HStack(spacing: 18) {
                    PhotosPicker(selection: $selectedPhotos, maxSelectionCount: 5, matching: .images) {
                        Label("Fotos", systemImage: "photo.on.rectangle")
                    }
                    if UIImagePickerController.isSourceTypeAvailable(.camera) {
                        Button { showCamera = true } label: { Label("Kamera", systemImage: "camera") }
                    }
                }.disabled(isUploading)

                if detail.attachments.isEmpty {
                    Text("Noch keine Fotos oder Dokumente vorhanden.").foregroundStyle(.secondary)
                } else {
                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 105), spacing: 10)], spacing: 10) {
                        ForEach(detail.attachments) { attachment in
                            if attachment.isImage {
                                ProtectedAttachmentImage(attachmentID: attachment.id, api: session.api)
                                    .frame(height: 105)
                                    .clipShape(RoundedRectangle(cornerRadius: 10))
                                    .overlay(alignment: .bottom) {
                                        Text(attachment.originalName).font(.caption2).lineLimit(1).padding(5).frame(maxWidth: .infinity).background(.ultraThinMaterial)
                                    }
                            } else {
                                VStack(spacing: 8) {
                                    Image(systemName: attachment.isPDF ? "doc.fill" : "doc").font(.title)
                                    Text(attachment.originalName).font(.caption2).lineLimit(2)
                                }
                                .frame(maxWidth: .infinity, minHeight: 105)
                                .background(Color.mfBackground)
                                .clipShape(RoundedRectangle(cornerRadius: 10))
                            }
                        }
                    }
                }
            }
        }
    }

    private func messagesCard(_ detail: CaseDetailResponse) -> some View {
        MFCard {
            VStack(alignment: .leading, spacing: 12) {
                Label("Nachrichten", systemImage: "bubble.left.and.bubble.right").font(.headline)
                if detail.messages.isEmpty { Text("Noch keine Nachrichten.").foregroundStyle(.secondary) }
                ForEach(detail.messages) { message in
                    VStack(alignment: .leading, spacing: 3) {
                        Text(message.message)
                        HStack {
                            if let actor = message.actorName { Text(actor) }
                            Spacer()
                            if let created = message.createdAt { Text(displayDateTime(created)) }
                        }.font(.caption).foregroundStyle(.secondary)
                    }
                    if message.id != detail.messages.last?.id { Divider() }
                }
                HStack {
                    TextField("Nachricht schreiben …", text: $messageText, axis: .vertical).lineLimit(1...4).textFieldStyle(.roundedBorder)
                    Button { Task { await sendMessage() } } label: {
                        if isSendingMessage { ProgressView() } else { Image(systemName: "paperplane.fill") }
                    }.disabled(messageText.trimmed.isEmpty || isSendingMessage)
                }
            }
        }
    }

    private func historyCard(_ detail: CaseDetailResponse) -> some View {
        MFCard {
            VStack(alignment: .leading, spacing: 12) {
                Label("Verlauf", systemImage: "clock.arrow.circlepath").font(.headline)
                if detail.events.isEmpty { Text("Noch keine Verlaufseinträge.").foregroundStyle(.secondary) }
                else {
                    ForEach(detail.events.prefix(20)) { event in
                        VStack(alignment: .leading, spacing: 3) {
                            Text(event.note ?? event.eventType ?? "Aktualisierung").font(.subheadline)
                            HStack {
                                if let actor = event.actorName { Text(actor) }
                                Spacer()
                                if let created = event.createdAt { Text(displayDateTime(created)) }
                            }.font(.caption).foregroundStyle(.secondary)
                        }
                        if event.id != detail.events.prefix(20).last?.id { Divider() }
                    }
                }
            }
        }
    }

    @MainActor private func reload() async {
        isLoading = true; errorMessage = nil
        do { detail = try await session.api.caseDetail(id: caseID) } catch { errorMessage = error.localizedDescription }
        isLoading = false
    }

    @MainActor private func uploadSelected(_ items: [PhotosPickerItem]) async {
        var files: [UploadFile] = []
        for item in items.prefix(5) {
            if let data = try? await item.loadTransferable(type: Data.self),
               let image = UIImage(data: data),
               let draft = draftImage(from: image, prefix: "mediathek") {
                files.append(draft.uploadFile)
            }
        }
        selectedPhotos = []
        await upload(files)
    }

    @MainActor private func upload(_ files: [UploadFile]) async {
        guard !files.isEmpty else { return }
        isUploading = true; errorMessage = nil
        do {
            _ = try await session.api.uploadImages(caseID: caseID, files: files)
            detail = try await session.api.caseDetail(id: caseID)
        } catch { errorMessage = error.localizedDescription }
        isUploading = false
    }

    @MainActor private func sendMessage() async {
        let text = messageText.trimmed
        guard !text.isEmpty else { return }
        isSendingMessage = true
        do {
            _ = try await session.api.sendMessage(caseID: caseID, message: text)
            messageText = ""
            detail = try await session.api.caseDetail(id: caseID)
        } catch { errorMessage = error.localizedDescription }
        isSendingMessage = false
    }

    @MainActor private func preparePDF() async {
        isPreparingPDF = true
        do {
            let data = try await session.api.casePDFData(id: caseID)
            let url = FileManager.default.temporaryDirectory.appendingPathComponent("MaengelFix-\(caseID.prefix(8)).pdf")
            try data.write(to: url, options: .atomic)
            pdfItem = PDFItem(url: url)
        } catch { errorMessage = error.localizedDescription }
        isPreparingPDF = false
    }

    private func displayDate(_ raw: String) -> String {
        String(raw.prefix(10)).split(separator: "-").reversed().joined(separator: ".")
    }

    private func displayDateTime(_ raw: String) -> String {
        let formatter = ISO8601DateFormatter()
        if let date = formatter.date(from: raw) { return date.formatted(date: .abbreviated, time: .shortened) }
        return raw
    }
}

private struct CaseEditView: View {
    @Environment(AppSession.self) private var session
    @Environment(\.dismiss) private var dismiss
    let item: DefectCase
    let onSaved: (DefectCase) -> Void

    @State private var title: String
    @State private var description: String
    @State private var category: String
    @State private var propertyLabel: String
    @State private var locationLabel: String
    @State private var recipientName: String
    @State private var recipientEmail: String
    @State private var recipientAddress: String
    @State private var status: String
    @State private var hasDeadline: Bool
    @State private var deadline: Date
    @State private var isSaving = false
    @State private var errorMessage: String?

    private let statuses = [("draft","Entwurf"),("sent","Versendet"),("reply","Rückmeldung"),("received","Eingegangen"),("reviewing","In Prüfung"),("commissioned","Beauftragt"),("scheduled","Terminiert"),("in_progress","In Bearbeitung"),("resolved","Erledigt")]

    init(item: DefectCase, onSaved: @escaping (DefectCase) -> Void) {
        self.item = item; self.onSaved = onSaved
        _title = State(initialValue: item.title)
        _description = State(initialValue: item.description ?? "")
        _category = State(initialValue: item.category ?? "Sonstiges")
        _propertyLabel = State(initialValue: item.propertyLabel ?? "")
        _locationLabel = State(initialValue: item.locationLabel ?? "")
        _recipientName = State(initialValue: item.recipientName ?? "")
        _recipientEmail = State(initialValue: item.recipientEmail ?? "")
        _recipientAddress = State(initialValue: item.recipientAddress ?? "")
        _status = State(initialValue: item.status)
        _hasDeadline = State(initialValue: item.deadlineOn?.isEmpty == false)
        let parsed = item.deadlineOn.flatMap { Self.apiDate.date(from: String($0.prefix(10))) } ?? Date().addingTimeInterval(7 * 86400)
        _deadline = State(initialValue: parsed)
    }

    var body: some View {
        Form {
            Section("Mangel") {
                TextField("Titel", text: $title)
                TextField("Kategorie", text: $category)
                TextEditor(text: $description).frame(minHeight: 120)
                Picker("Status", selection: $status) {
                    ForEach(statuses, id: \.0) { Text($0.1).tag($0.0) }
                }
            }
            Section("Ort") {
                TextField("Objekt / Adresse", text: $propertyLabel)
                TextField("Raum / Ort", text: $locationLabel)
            }
            Section("Empfänger") {
                TextField("Name / Firma", text: $recipientName)
                TextField("E-Mail", text: $recipientEmail).keyboardType(.emailAddress).textInputAutocapitalization(.never)
                TextField("Anschrift", text: $recipientAddress, axis: .vertical).lineLimit(2...4)
            }
            Section("Frist") {
                Toggle("Frist setzen", isOn: $hasDeadline)
                if hasDeadline { DatePicker("Frist bis", selection: $deadline, displayedComponents: .date) }
            }
            if let errorMessage { Section { Text(errorMessage).foregroundStyle(.red) } }
        }
        .navigationTitle("Bearbeiten")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .cancellationAction) { Button("Abbrechen") { dismiss() } }
            ToolbarItem(placement: .confirmationAction) {
                Button("Speichern") { Task { await save() } }
                    .disabled(isSaving || title.trimmed.isEmpty || description.trimmed.isEmpty)
            }
        }
    }

    @MainActor private func save() async {
        isSaving = true; errorMessage = nil
        do {
            let updated = try await session.api.updateCase(id: item.id, input: UpdateCaseRequest(
                title: title.trimmed, category: category.trimmed, description: description.trimmed,
                propertyLabel: propertyLabel, locationLabel: locationLabel, discoveredOn: nil,
                recipientName: recipientName, recipientEmail: recipientEmail, recipientAddress: recipientAddress,
                deadlineOn: hasDeadline ? Self.apiDate.string(from: deadline) : nil, status: status
            ))
            onSaved(updated)
        } catch { errorMessage = error.localizedDescription }
        isSaving = false
    }

    private static let apiDate: DateFormatter = {
        let f = DateFormatter(); f.calendar = Calendar(identifier: .gregorian); f.locale = Locale(identifier: "en_US_POSIX"); f.dateFormat = "yyyy-MM-dd"; return f
    }()
}

private struct PDFItem: Identifiable {
    let id = UUID()
    let url: URL
}

private struct PDFPreview: UIViewControllerRepresentable {
    let url: URL
    func makeCoordinator() -> Coordinator { Coordinator(url: url) }
    func makeUIViewController(context: Context) -> UINavigationController {
        let controller = QLPreviewController()
        controller.dataSource = context.coordinator
        controller.navigationItem.rightBarButtonItem = UIBarButtonItem(barButtonSystemItem: .action, target: context.coordinator, action: #selector(Coordinator.share))
        context.coordinator.controller = controller
        return UINavigationController(rootViewController: controller)
    }
    func updateUIViewController(_ uiViewController: UINavigationController, context: Context) {}

    final class Coordinator: NSObject, QLPreviewControllerDataSource {
        let url: URL
        weak var controller: UIViewController?
        init(url: URL) { self.url = url }
        func numberOfPreviewItems(in controller: QLPreviewController) -> Int { 1 }
        func previewController(_ controller: QLPreviewController, previewItemAt index: Int) -> QLPreviewItem { url as NSURL }
        @objc func share() {
            guard let controller else { return }
            controller.present(UIActivityViewController(activityItems: [url], applicationActivities: nil), animated: true)
        }
    }
}
