import SwiftUI
import PhotosUI
import UIKit

struct CreateCaseView: View {
    @Environment(AppSession.self) private var session
    let onCreated: (DefectCase) -> Void

    @State private var title = ""
    @State private var description = ""
    @State private var context = "housing"
    @State private var category = "Feuchtigkeit / Schimmel"
    @State private var propertyLabel = ""
    @State private var locationLabel = ""
    @State private var recipientName = ""
    @State private var recipientEmail = ""
    @State private var recipientAddress = ""
    @State private var discoveredOn = Date()
    @State private var hasDeadline = false
    @State private var deadlineOn = Date().addingTimeInterval(7 * 86400)
    @State private var selectedPhotos: [PhotosPickerItem] = []
    @State private var draftImages: [DraftImage] = []
    @State private var showCamera = false
    @State private var isSubmitting = false
    @State private var errorMessage: String?
    @FocusState private var focusedField: Field?

    private enum Field: Hashable { case title, description, property, location, recipientName, recipientEmail, recipientAddress }

    private let contexts: [(String, String)] = [
        ("housing", "Wohnen / Immobilie"), ("delivery", "Lieferung"), ("product", "Produkt"),
        ("service", "Dienstleistung"), ("vehicle", "Fahrzeug"), ("travel", "Reise"), ("other", "Sonstiges")
    ]

    private let categories: [String: [String]] = [
        "housing": ["Feuchtigkeit / Schimmel", "Heizung / Warmwasser", "Sanitär", "Elektro", "Fenster / Türen", "Boden / Wand", "Lärm", "Außenbereich", "Schädlingsbefall", "Sonstiges"],
        "delivery": ["Transportschaden", "Verpackung beschädigt", "Produkt beschädigt", "Falsche Lieferung", "Fehlteil / unvollständig", "Lieferung verspätet", "Sonstiges"],
        "product": ["Beschädigung", "Funktionsmangel", "Qualitätsmangel", "Fehlteil / unvollständig", "Falsches Produkt / Variante", "Material- / Verarbeitungsfehler", "Software / Firmware", "Sonstiges"],
        "service": ["Ausführung mangelhaft", "Leistung unvollständig", "Beschädigung verursacht", "Abweichung vom Auftrag", "Funktionsmangel nach Ausführung", "Termin / Verzögerung", "Sonstiges"],
        "vehicle": ["Motor / Antrieb", "Bremsen", "Fahrwerk / Lenkung", "Elektrik / Elektronik", "Karosserie / Lack", "Innenraum", "Klima / Heizung", "Reifen / Räder", "Undichtigkeit", "Werkstattleistung", "Sonstiges"],
        "travel": ["Unterkunft / Zimmer", "Sauberkeit / Hygiene", "Ausstattung defekt / fehlt", "Lärm", "Klima / Heizung", "Sanitär", "Verpflegung", "Transport / Transfer", "Buchung / Leistung abweichend", "Sicherheit", "Sonstiges"],
        "other": ["Beschädigung", "Funktionsmangel", "Qualitätsmangel", "Fehlteil / unvollständig", "Falsche Lieferung / Ausführung", "Sonstiges"]
    ]

    var body: some View {
        NavigationStack {
            Form {
                Section("Mangel") {
                    TextField("Titel", text: $title).focused($focusedField, equals: .title)
                    Picker("Bereich", selection: $context) {
                        ForEach(contexts, id: \.0) { value, label in Text(label).tag(value) }
                    }
                    .onChange(of: context) { _, value in category = categories[value]?.first ?? "Sonstiges" }
                    Picker("Kategorie", selection: $category) {
                        ForEach(categories[context] ?? ["Sonstiges"], id: \.self) { Text($0).tag($0) }
                    }
                    DatePicker("Festgestellt am", selection: $discoveredOn, displayedComponents: .date)
                }

                Section("Beschreibung") {
                    TextEditor(text: $description).frame(minHeight: 140).focused($focusedField, equals: .description)
                }

                Section("Fotos") {
                    HStack {
                        PhotosPicker(selection: $selectedPhotos, maxSelectionCount: max(0, 5 - draftImages.count), matching: .images) {
                            Label("Mediathek", systemImage: "photo.on.rectangle")
                        }
                        Spacer()
                        if UIImagePickerController.isSourceTypeAvailable(.camera) {
                            Button { showCamera = true } label: { Label("Kamera", systemImage: "camera") }
                                .disabled(draftImages.count >= 5)
                        }
                    }
                    DraftImageStrip(images: draftImages) { id in draftImages.removeAll { $0.id == id } }
                    if !draftImages.isEmpty { Text("\(draftImages.count) von maximal 5 Fotos ausgewählt").font(.caption).foregroundStyle(.secondary) }
                }

                Section("Ort / Bezug") {
                    TextField("Objekt / Adresse (optional)", text: $propertyLabel).focused($focusedField, equals: .property)
                    TextField("Raum / Ort (optional)", text: $locationLabel).focused($focusedField, equals: .location)
                }

                Section("Empfänger") {
                    TextField("Name / Firma (optional)", text: $recipientName).focused($focusedField, equals: .recipientName)
                    TextField("E-Mail (optional)", text: $recipientEmail).keyboardType(.emailAddress).textInputAutocapitalization(.never).focused($focusedField, equals: .recipientEmail)
                    TextField("Anschrift (optional)", text: $recipientAddress, axis: .vertical).lineLimit(2...4).focused($focusedField, equals: .recipientAddress)
                }

                Section("Frist") {
                    Toggle("Frist setzen", isOn: $hasDeadline)
                    if hasDeadline { DatePicker("Frist bis", selection: $deadlineOn, displayedComponents: .date) }
                    if hasDeadline { Text("Fristen sind bei Privatkonten eine Pro-Funktion.").font(.caption).foregroundStyle(.secondary) }
                }

                if let errorMessage { Section { Text(errorMessage).foregroundStyle(.red) } }
            }
            .navigationTitle("Neuer Mangel")
            .scrollDismissesKeyboard(.interactively)
            .onChange(of: selectedPhotos) { _, items in Task { await loadSelected(items) } }
            .sheet(isPresented: $showCamera) {
                CameraPicker { image in if let draft = draftImage(from: image), draftImages.count < 5 { draftImages.append(draft) } }
                    .ignoresSafeArea()
            }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Anlegen") { submit() }.fontWeight(.semibold).disabled(isSubmitting || !formIsValid)
                }
                ToolbarItemGroup(placement: .keyboard) { Spacer(); Button("Fertig") { focusedField = nil } }
            }
            .safeAreaInset(edge: .bottom) {
                VStack(spacing: 0) {
                    Divider()
                    Button { submit() } label: {
                        HStack(spacing: 10) {
                            if isSubmitting { ProgressView() } else { Image(systemName: "checkmark.circle.fill") }
                            Text(isSubmitting ? "Wird angelegt …" : "Mangel anlegen").fontWeight(.bold)
                        }
                        .frame(maxWidth: .infinity).padding(.vertical, 14)
                    }
                    .buttonStyle(.borderedProminent).disabled(isSubmitting || !formIsValid).padding(.horizontal).padding(.vertical, 10)
                }.background(.bar)
            }
        }
    }

    private var formIsValid: Bool {
        !title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !description.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    @MainActor
    private func loadSelected(_ items: [PhotosPickerItem]) async {
        for item in items where draftImages.count < 5 {
            if let data = try? await item.loadTransferable(type: Data.self), let image = UIImage(data: data), let draft = draftImage(from: image, prefix: "mediathek") {
                draftImages.append(draft)
            }
        }
        selectedPhotos = []
    }

    private func submit() {
        guard formIsValid, !isSubmitting else { return }
        focusedField = nil
        isSubmitting = true
        errorMessage = nil
        Task {
            do {
                let created = try await session.api.createCase(CreateCaseRequest(
                    title: title.trimmed, description: description.trimmed, caseContext: context, category: category,
                    propertyLabel: propertyLabel.nilIfBlank, locationLabel: locationLabel.nilIfBlank,
                    discoveredOn: Self.apiDate.string(from: discoveredOn), recipientName: recipientName.nilIfBlank,
                    recipientEmail: recipientEmail.nilIfBlank, recipientAddress: recipientAddress.nilIfBlank,
                    deadlineOn: hasDeadline ? Self.apiDate.string(from: deadlineOn) : nil, destinationLinkId: nil
                ))
                if !draftImages.isEmpty {
                    do { _ = try await session.api.uploadImages(caseID: created.id, files: draftImages.map(\.uploadFile)) }
                    catch { }
                }
                reset()
                onCreated(created)
            } catch {
                errorMessage = error.localizedDescription
            }
            isSubmitting = false
        }
    }

    private func reset() {
        title = ""; description = ""; context = "housing"; category = categories["housing"]?.first ?? "Sonstiges"
        propertyLabel = ""; locationLabel = ""; recipientName = ""; recipientEmail = ""; recipientAddress = ""
        discoveredOn = Date(); hasDeadline = false; deadlineOn = Date().addingTimeInterval(7 * 86400); draftImages = []; selectedPhotos = []
    }

    private static let apiDate: DateFormatter = { let f = DateFormatter(); f.calendar = Calendar(identifier: .gregorian); f.locale = Locale(identifier: "en_US_POSIX"); f.dateFormat = "yyyy-MM-dd"; return f }()
}

extension String {
    var trimmed: String { trimmingCharacters(in: .whitespacesAndNewlines) }
    var nilIfBlank: String? { let value = trimmed; return value.isEmpty ? nil : value }
}

struct DraftImage: Identifiable, Hashable {
    let id = UUID()
    let data: Data
    let fileName: String
    let mimeType: String
    var uploadFile: UploadFile { UploadFile(data: data, fileName: fileName, mimeType: mimeType) }
}

@MainActor
func draftImage(from image: UIImage, prefix: String = "foto") -> DraftImage? {
    guard let data = image.jpegData(compressionQuality: 0.86) else { return nil }
    return DraftImage(data: data, fileName: "\(prefix)-\(UUID().uuidString.prefix(8)).jpg", mimeType: "image/jpeg")
}

struct DraftImageStrip: View {
    let images: [DraftImage]
    let remove: (UUID) -> Void
    var body: some View {
        if !images.isEmpty {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 10) {
                    ForEach(images) { item in
                        ZStack(alignment: .topTrailing) {
                            if let uiImage = UIImage(data: item.data) {
                                Image(uiImage: uiImage).resizable().scaledToFill().frame(width: 90, height: 90).clipShape(RoundedRectangle(cornerRadius: 10))
                            }
                            Button { remove(item.id) } label: {
                                Image(systemName: "xmark.circle.fill").symbolRenderingMode(.palette).foregroundStyle(.white, .black.opacity(0.7))
                            }.padding(4)
                        }
                    }
                }
            }
        }
    }
}

struct CameraPicker: UIViewControllerRepresentable {
    @Environment(\.dismiss) private var dismiss
    let onImage: (UIImage) -> Void
    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController(); picker.sourceType = .camera; picker.delegate = context.coordinator; picker.allowsEditing = false; return picker
    }
    func updateUIViewController(_ uiViewController: UIImagePickerController, context: Context) {}
    func makeCoordinator() -> Coordinator { Coordinator(parent: self) }
    final class Coordinator: NSObject, UINavigationControllerDelegate, UIImagePickerControllerDelegate {
        let parent: CameraPicker
        init(parent: CameraPicker) { self.parent = parent }
        func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
            if let image = info[.originalImage] as? UIImage { parent.onImage(image) }; parent.dismiss()
        }
        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) { parent.dismiss() }
    }
}

struct ProtectedAttachmentImage: View {
    let attachmentID: String
    let api: APIClient
    @State private var image: UIImage?
    @State private var failed = false
    var body: some View {
        Group {
            if let image { Image(uiImage: image).resizable().scaledToFill() }
            else if failed { Image(systemName: "photo.badge.exclamationmark").foregroundStyle(.secondary) }
            else { ProgressView() }
        }
        .task(id: attachmentID) {
            do { image = UIImage(data: try await api.attachmentData(id: attachmentID)) } catch { failed = true }
        }
    }
}
