import SwiftUI

struct CreateCaseView: View {
    @Environment(AppSession.self) private var session
    let onCreated: (DefectCase) -> Void

    @State private var title = ""
    @State private var description = ""
    @State private var context = "housing"
    @State private var category = "Feuchtigkeit / Schimmel"
    @State private var propertyLabel = ""
    @State private var locationLabel = ""
    @State private var isSubmitting = false
    @State private var errorMessage: String?

    private let contexts: [(String, String)] = [
        ("housing", "Wohnen / Immobilie"),
        ("delivery", "Lieferung"),
        ("product", "Produkt"),
        ("service", "Dienstleistung"),
        ("vehicle", "Fahrzeug"),
        ("travel", "Reise"),
        ("other", "Sonstiges")
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
                    TextField("Titel", text: $title)
                    Picker("Bereich", selection: $context) {
                        ForEach(contexts, id: \.0) { value, label in
                            Text(label).tag(value)
                        }
                    }
                    .onChange(of: context) { _, newValue in
                        category = categories[newValue]?.first ?? "Sonstiges"
                    }
                    Picker("Kategorie", selection: $category) {
                        ForEach(categories[context] ?? ["Sonstiges"], id: \.self) { value in
                            Text(value).tag(value)
                        }
                    }
                }

                Section("Beschreibung") {
                    TextEditor(text: $description)
                        .frame(minHeight: 150)
                }

                Section("Ort / Bezug") {
                    TextField("Objekt / Adresse (optional)", text: $propertyLabel)
                    TextField("Raum / Ort (optional)", text: $locationLabel)
                }

                if let errorMessage {
                    Section {
                        Text(errorMessage)
                            .foregroundStyle(.red)
                    }
                }

                Section {
                    Button {
                        submit()
                    } label: {
                        HStack {
                            Spacer()
                            if isSubmitting { ProgressView() }
                            Text("Mangel anlegen").fontWeight(.bold)
                            Spacer()
                        }
                    }
                    .disabled(isSubmitting || !formIsValid)
                }
            }
            .navigationTitle("Neuer Mangel")
        }
    }

    private var formIsValid: Bool {
        !title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
        !description.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    private func submit() {
        guard formIsValid else { return }
        isSubmitting = true
        errorMessage = nil

        Task {
            defer { isSubmitting = false }
            do {
                let created = try await session.api.createCase(
                    CreateCaseRequest(
                        title: title,
                        description: description,
                        caseContext: context,
                        category: category,
                        propertyLabel: propertyLabel.nilIfBlank,
                        locationLabel: locationLabel.nilIfBlank,
                        recipientName: nil,
                        recipientEmail: nil,
                        recipientAddress: nil,
                        deadlineOn: nil,
                        destinationLinkId: nil
                    )
                )
                reset()
                onCreated(created)
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }

    private func reset() {
        title = ""
        description = ""
        context = "housing"
        category = categories["housing"]?.first ?? "Sonstiges"
        propertyLabel = ""
        locationLabel = ""
    }
}

private extension String {
    var nilIfBlank: String? {
        let trimmed = trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}
