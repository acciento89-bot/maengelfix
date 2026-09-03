export const SITE_URL = 'https://maengelfix.kamilunavo.com';

export const SEO_PAGES = {
  '/maengelanzeige-erstellen': {
    locale: 'de', alternate: '/en/create-defect-report',
    eyebrow: 'MÄNGELANZEIGE ERSTELLEN',
    title: 'Mängelanzeige erstellen – vollständig und nachvollziehbar',
    description: 'Dokumentiere einen Mangel mit Fotos, Datum, Empfänger und Frist. MängelFix erstellt daraus eine übersichtliche PDF-Mängelanzeige.',
    lead: 'Halte alle wichtigen Angaben direkt beim Auftreten fest. MängelFix bündelt Beschreibung, Fotobelege, Empfänger und Verlauf in einem geordneten Vorgang.',
    intent: 'Für Mietmängel, beschädigte Lieferungen, fehlerhafte Produkte, Werkstattleistungen, Reisen und Dienstleistungen.',
    steps: [
      ['Mangel beschreiben', 'Notiere sachlich, was betroffen ist, wo der Mangel auftritt und wann du ihn festgestellt hast.'],
      ['Belege zuordnen', 'Füge Fotos und weitere Informationen direkt dem passenden Vorgang hinzu.'],
      ['Empfänger und Frist erfassen', 'Hinterlege Vermieter, Händler, Werkstatt oder Dienstleister und behalte gewünschte Rückmeldetermine im Blick.'],
      ['PDF erstellen', 'Erzeuge eine übersichtliche Dokumentation, prüfe sie und nutze sie für deine weitere Kommunikation.']
    ],
    benefits: ['Alle Angaben an einem Ort', 'Fotobelege direkt am Vorgang', 'Nachvollziehbare PDF-Dokumentation', 'Status und Verlauf dauerhaft geordnet'],
    faq: [
      ['Kann ich MängelFix kostenlos nutzen?', 'Ja. Privat Free eignet sich für bis zu fünf aktive Vorgänge und enthält die grundlegende Erfassung, Fotos und eine Basis-PDF.'],
      ['Ersetzt MängelFix eine Rechtsberatung?', 'Nein. MängelFix hilft bei Organisation und Dokumentation, nimmt aber keine rechtliche Bewertung deines Falls vor.'],
      ['Muss der Empfänger MängelFix verwenden?', 'Nein. Du kannst einen Empfänger manuell eintragen und die erstellte Dokumentation unabhängig versenden.']
    ]
  },
  '/mietmangel-dokumentieren': {
    locale: 'de', alternate: '/en/rental-defect-documentation',
    eyebrow: 'MIETMANGEL DOKUMENTIEREN',
    title: 'Mietmangel dokumentieren – Fotos, Fristen und Verlauf geordnet',
    description: 'Mietmängel strukturiert erfassen: Fotos sichern, Räume zuordnen, Vermieter hinterlegen, Fristen im Blick behalten und PDF erstellen.',
    lead: 'Ob Heizungsausfall, Feuchtigkeit, Schimmel oder ein defektes Fenster: Eine saubere Dokumentation hilft dir, später nichts aus dem Gedächtnis rekonstruieren zu müssen.',
    intent: 'Für Mieter, Eigentümer und Hausverwaltungen – vom ersten Foto bis zur erledigten Rückmeldung.',
    steps: [
      ['Ort und Zeitpunkt festhalten', 'Ordne den Mangel einer Wohnung oder einem Raum zu und erfasse das Feststellungsdatum.'],
      ['Zustand fotografieren', 'Sichere aussagekräftige Übersichts- und Detailbilder und lasse sie direkt beim Vorgang.'],
      ['Vermieter oder Verwaltung eintragen', 'Speichere den richtigen Empfänger und ergänze eine gewünschte Rückmeldefrist.'],
      ['Reaktionen nachhalten', 'Dokumentiere Antworten, Termine, Notizen und Statusänderungen in einem chronologischen Verlauf.']
    ],
    benefits: ['Räume und Objekte eindeutig zuordnen', 'Fotos chronologisch sichern', 'Fristen separat sichtbar machen', 'Kommunikationsverlauf nachvollziehen'],
    faq: [
      ['Welche Mietmängel kann ich dokumentieren?', 'Zum Beispiel Feuchtigkeit, Schimmel, Heizung und Warmwasser, Sanitär, Elektro, Fenster, Türen, Lärm oder Schäden im Außenbereich.'],
      ['Kann meine Hausverwaltung den Vorgang digital erhalten?', 'Wenn deine Verwaltung MängelFix nutzt und dich verknüpft hat, kannst du den Mangel direkt übermitteln. Alternativ dokumentierst du ihn privat.'],
      ['Kann ich Fotos in die PDF übernehmen?', 'Ja. Fotobelege können dem Vorgang zugeordnet und in der Dokumentation berücksichtigt werden.']
    ]
  },
  '/lieferung-beschaedigt': {
    locale: 'de', alternate: '/en/damaged-delivery',
    eyebrow: 'BESCHÄDIGTE LIEFERUNG',
    title: 'Lieferung beschädigt? Schaden sofort sauber dokumentieren',
    description: 'Beschädigte Lieferung mit Verpackung, Produkt, Bestellnummer, Fotos und gewünschter Lösung dokumentieren und als PDF sichern.',
    lead: 'Fotografiere Verpackung und Inhalt, notiere Bestell- oder Sendungsnummer und halte fest, welche Lösung du erwartest. So bleibt der gesamte Reklamationsvorgang zusammen.',
    intent: 'Für Transportschäden, beschädigte Verpackungen, Fehlteile, falsche Produkte und unvollständige Lieferungen.',
    steps: [
      ['Verpackung und Produkt fotografieren', 'Sichere zuerst den ungeöffneten oder unmittelbar vorgefundenen Zustand und anschließend die Details.'],
      ['Bestellung zuordnen', 'Erfasse Bestellnummer, Lieferdatum, Händler und den konkret betroffenen Artikel.'],
      ['Gewünschte Lösung notieren', 'Halte fest, ob du Reparatur, Ersatz, Rückerstattung oder eine andere Lösung anstrebst.'],
      ['Reklamation nachhalten', 'Bewahre Rückmeldungen, Fristen und den aktuellen Status übersichtlich im selben Vorgang auf.']
    ],
    benefits: ['Verpackung und Schaden gemeinsam belegen', 'Bestellbezug nicht verlieren', 'Gewünschte Lösung festhalten', 'Reklamationsverlauf zentral speichern'],
    faq: [
      ['Kann ich mehrere Fotos hinzufügen?', 'Ja. Bereits Privat Free ermöglicht Fotobelege; erweiterte Dokumentation steht in Privat Pro zur Verfügung.'],
      ['Kann ich auch ein fehlendes Teil erfassen?', 'Ja. Neben Transportschäden lassen sich auch Fehlteile, falsche oder unvollständige Lieferungen dokumentieren.'],
      ['Versendet MängelFix die Reklamation automatisch?', 'Du erstellst und prüfst deine Dokumentation selbst und entscheidest anschließend, wie du sie an den Empfänger übermittelst.']
    ]
  },
  '/handwerkermangel-dokumentieren': {
    locale: 'de', alternate: '/en/contractor-defect-documentation',
    eyebrow: 'HANDWERKERLEISTUNG DOKUMENTIEREN',
    title: 'Handwerkermangel dokumentieren und Nachbesserung organisieren',
    description: 'Mangelhafte Handwerkerleistung mit Auftrag, Ausführungsort, Fotos, Rechnungsbezug und gewünschter Nachbesserung dokumentieren.',
    lead: 'Wenn eine Leistung unvollständig, beschädigend oder anders als beauftragt ausgeführt wurde, hält MängelFix Auftrag, Zustand und weitere Schritte in einem Vorgang zusammen.',
    intent: 'Für private Auftraggeber, Eigentümer, Verwaltungen und professionelle Objektteams.',
    steps: [
      ['Leistung konkret benennen', 'Beschreibe ohne Wertung, welche vereinbarte oder ausgeführte Arbeit betroffen ist.'],
      ['Ausführungsort und Belege erfassen', 'Ordne Fotos, Auftrags- oder Rechnungsnummer und relevante Daten dem Vorgang zu.'],
      ['Nachbesserung festhalten', 'Notiere die gewünschte Lösung und einen Termin für die erwartete Rückmeldung.'],
      ['Fortschritt dokumentieren', 'Halte Termine, Antworten, neue Fotos und den Abschluss chronologisch fest.']
    ],
    benefits: ['Auftragsbezug eindeutig sichern', 'Vorher/Nachher nachvollziehbar halten', 'Nachbesserung strukturiert begleiten', 'Dokumentation als PDF bündeln'],
    faq: [
      ['Ist MängelFix nur für Gebäudearbeiten gedacht?', 'Nein. Du kannst unterschiedliche Dienstleistungen und Handwerkerleistungen dokumentieren.'],
      ['Können Hausverwaltungen Dienstleister einbinden?', 'Ja. Verwaltungsarbeitsbereiche können Dienstleister, Arbeitsaufträge, Termine und Rückmeldungen organisieren.'],
      ['Bewertet MängelFix, ob ein Anspruch besteht?', 'Nein. Die Anwendung dokumentiert deine Angaben und ersetzt keine rechtliche oder sachverständige Prüfung.']
    ]
  },
  '/hausverwaltung-maengelmanagement': {
    locale: 'de', alternate: '/en/property-defect-management',
    eyebrow: 'MÄNGELMANAGEMENT FÜR HAUSVERWALTUNGEN',
    title: 'Mängelmanagement für Hausverwaltungen – vom Eingang bis zur Erledigung',
    description: 'Mietmängel, Objekte, Einheiten, Zuständigkeiten, Fristen, Handwerkeraufträge und Übergabeprotokolle zentral verwalten.',
    lead: 'MängelFix schafft einen gemeinsamen Arbeitsbereich für eingehende Mietermeldungen, interne Zuständigkeiten und externe Dienstleister.',
    intent: 'Planbar nach verwalteten Einheiten – unabhängig davon, wie viele Mängel gemeldet werden.',
    steps: [
      ['Meldungen strukturiert empfangen', 'Ordne eingehende Vorgänge direkt einem Objekt, einer Einheit und dem zuständigen Teammitglied zu.'],
      ['Prioritäten und Fristen steuern', 'Behalte offene Aufgaben, Termine und fällige Rückmeldungen in zentralen Ansichten im Blick.'],
      ['Dienstleister beauftragen', 'Erstelle Arbeitsaufträge und erhalte Rückmeldungen über einen sicheren externen Zugriff.'],
      ['Erledigung nachweisen', 'Dokumentiere Verlauf, Arbeitsfotos und Abschluss nachvollziehbar für Team und Bestand.']
    ],
    benefits: ['Objekte und Einheiten zentral organisiert', 'Rollen und Zuständigkeiten im Team', 'Arbeitsaufträge mit Dienstleister-Rückmeldung', 'Audit-Log, Protokolle und Auswertungen'],
    faq: [
      ['Wie wird der Verwaltungstarif berechnet?', 'Die Tarife richten sich nach der Anzahl separat verwalteter Wohn- oder Gewerbeeinheiten, nicht nach der Zahl gemeldeter Mängel.'],
      ['Brauchen Handwerker ein MängelFix-Konto?', 'Nein. Beauftragte Dienstleister können einen freigegebenen Arbeitsauftrag über einen sicheren Link bearbeiten.'],
      ['Kann ich MängelFix vorab testen?', 'Ja. Der Verwaltungsbereich kann 14 Tage kostenlos getestet werden.']
    ]
  }
};

const english = {
  '/en/create-defect-report': ['/maengelanzeige-erstellen', 'CREATE A DEFECT REPORT', 'Create a clear defect report with photos and a complete timeline', 'Document a defect with photos, dates, recipient details and follow-up deadlines. MängelFix turns your information into a clear PDF record.', 'Capture every relevant detail as soon as a problem occurs. MängelFix keeps the description, evidence, recipient and timeline together in one organized case.', 'For rental issues, damaged deliveries, faulty products, workshop work, travel and services.'],
  '/en/rental-defect-documentation': ['/mietmangel-dokumentieren', 'RENTAL DEFECT DOCUMENTATION', 'Document rental defects with photos, dates and a reliable timeline', 'Document rental defects, assign rooms, store landlord details, track follow-ups and create a clear PDF record.', 'From heating failures and damp to broken windows: keep facts, photos and responses together instead of reconstructing them later.', 'For tenants, owners and property managers.'],
  '/en/damaged-delivery': ['/lieferung-beschaedigt', 'DAMAGED DELIVERY', 'Damaged delivery? Record the condition before details get lost', 'Document damaged packaging, products, order details, photos and your preferred resolution in one organized case.', 'Photograph the packaging and contents, add the order or tracking reference and record the outcome you expect.', 'For transport damage, missing parts, incorrect items and incomplete deliveries.'],
  '/en/contractor-defect-documentation': ['/handwerkermangel-dokumentieren', 'CONTRACTOR WORK', 'Document defective contractor work and organize the follow-up', 'Record defective contractor work with job details, location, photos, invoice reference and the requested remedy.', 'Keep the original job, observed condition, evidence and every follow-up step together in one case.', 'For private clients, owners and property teams.'],
  '/en/property-defect-management': ['/hausverwaltung-maengelmanagement', 'PROPERTY DEFECT MANAGEMENT', 'Property defect management from first report to completion', 'Manage rental defects, properties, units, responsibilities, deadlines, contractor jobs and inspection reports centrally.', 'Give your team one workspace for tenant reports, internal ownership and external contractors.', 'Pricing is based on managed units, not the number of reported defects.']
};

for (const [path, [alternate, eyebrow, title, description, lead, intent]] of Object.entries(english)) {
  SEO_PAGES[path] = {
    locale: 'en', alternate, eyebrow, title, description, lead, intent,
    steps: [
      ['Capture the facts', 'Record what happened, where it occurred and when you first noticed it.'],
      ['Add supporting evidence', 'Keep photos and reference details directly with the relevant case.'],
      ['Set recipient and follow-up', 'Store the responsible party and keep the next expected response visible.'],
      ['Create a clear record', 'Generate an organized PDF and maintain a chronological case history.']
    ],
    benefits: ['One place for every detail', 'Photos attached to the right case', 'Clear PDF documentation', 'A traceable status and timeline'],
    faq: [
      ['Can I use MängelFix for free?', 'Yes. Private Free includes the core case workflow for up to five active cases, photo evidence and a basic PDF.'],
      ['Does MängelFix provide legal advice?', 'No. MängelFix supports documentation and organization but does not assess the legal merits of a case.'],
      ['Does the recipient need an account?', 'No. Private users can enter recipient details manually and share their documentation independently.']
    ]
  };
}

export const SEO_META = {
  '/': { locale: 'de', alternate: '/en', title: 'Mängel dokumentieren & nachhalten | MängelFix', description: 'Mängel strukturiert erfassen, Fotos und Fristen zuordnen, professionelle PDF-Unterlagen erstellen und den gesamten Verlauf nachhalten.' },
  '/en': { locale: 'en', alternate: '/', title: 'Document defects and keep every case organized | MängelFix', description: 'Capture defects, attach photos, track follow-ups and create professional PDF documentation for private cases and property management.' },
  ...Object.fromEntries(Object.entries(SEO_PAGES).map(([path, page]) => [path, { locale: page.locale, alternate: page.alternate, title: `${page.title} | MängelFix`, description: page.description }]))
};
