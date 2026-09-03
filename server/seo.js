const origin = 'https://maengelfix.kamilunavo.com';

const pages = {
  '/': ['de', '/en', 'Mängel dokumentieren & nachhalten | MängelFix', 'Mängel strukturiert erfassen, Fotos und Fristen zuordnen, professionelle PDF-Unterlagen erstellen und den gesamten Verlauf nachhalten.'],
  '/en': ['en', '/', 'Document defects and keep every case organized | MängelFix', 'Capture defects, attach photos, track follow-ups and create professional PDF documentation for private cases and property management.'],
  '/maengelanzeige-erstellen': ['de', '/en/create-defect-report', 'Mängelanzeige erstellen – vollständig und nachvollziehbar | MängelFix', 'Dokumentiere einen Mangel mit Fotos, Datum, Empfänger und Frist. MängelFix erstellt daraus eine übersichtliche PDF-Mängelanzeige.'],
  '/mietmangel-dokumentieren': ['de', '/en/rental-defect-documentation', 'Mietmangel dokumentieren – Fotos, Fristen und Verlauf | MängelFix', 'Mietmängel strukturiert erfassen: Fotos sichern, Räume zuordnen, Vermieter hinterlegen, Fristen im Blick behalten und PDF erstellen.'],
  '/lieferung-beschaedigt': ['de', '/en/damaged-delivery', 'Lieferung beschädigt? Schaden sauber dokumentieren | MängelFix', 'Beschädigte Lieferung mit Verpackung, Produkt, Bestellnummer, Fotos und gewünschter Lösung dokumentieren und als PDF sichern.'],
  '/handwerkermangel-dokumentieren': ['de', '/en/contractor-defect-documentation', 'Handwerkermangel dokumentieren und Nachbesserung organisieren | MängelFix', 'Mangelhafte Handwerkerleistung mit Auftrag, Ausführungsort, Fotos, Rechnungsbezug und gewünschter Nachbesserung dokumentieren.'],
  '/hausverwaltung-maengelmanagement': ['de', '/en/property-defect-management', 'Mängelmanagement für Hausverwaltungen | MängelFix', 'Mietmängel, Objekte, Einheiten, Zuständigkeiten, Fristen, Handwerkeraufträge und Übergabeprotokolle zentral verwalten.'],
  '/en/create-defect-report': ['en', '/maengelanzeige-erstellen', 'Create a defect report with photos and a clear timeline | MängelFix', 'Document a defect with photos, dates, recipient details and follow-up deadlines, then create a clear PDF record.'],
  '/en/rental-defect-documentation': ['en', '/mietmangel-dokumentieren', 'Document rental defects with photos and dates | MängelFix', 'Document rental defects, assign rooms, store landlord details, track follow-ups and create a clear PDF record.'],
  '/en/damaged-delivery': ['en', '/lieferung-beschaedigt', 'Damaged delivery? Record the condition clearly | MängelFix', 'Document damaged packaging, products, order details, photos and your preferred resolution in one organized case.'],
  '/en/contractor-defect-documentation': ['en', '/handwerkermangel-dokumentieren', 'Document defective contractor work | MängelFix', 'Record defective contractor work with job details, location, photos, invoice reference and the requested remedy.'],
  '/en/property-defect-management': ['en', '/hausverwaltung-maengelmanagement', 'Property defect management from report to completion | MängelFix', 'Manage rental defects, properties, units, responsibilities, deadlines, contractor jobs and inspection reports centrally.']
};

const clean = value => String(value).replace(/[&<>"']/g, character => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[character]));
const absolute = path => `${origin}${path === '/' ? '' : path}`;

export function renderSeoHtml(template, requestPath) {
  const normalizedPath = requestPath !== '/' ? requestPath.replace(/\/$/, '') : '/';
  const page = pages[normalizedPath];
  if (!page) {
    const privatePath = ['/app', '/anmelden', '/registrieren', '/einladung/', '/auftrag/', '/passwort-', '/email-bestaetigen/'].some(path => normalizedPath.startsWith(path));
    return privatePath ? template.replace('</head>', '    <meta name="robots" content="noindex, nofollow">\n  </head>') : template;
  }
  const [locale, alternate, title, description] = page;
  const dePath = locale === 'de' ? normalizedPath : alternate;
  const enPath = locale === 'en' ? normalizedPath : alternate;
  const canonical = absolute(normalizedPath);
  const schema = {
    '@context': 'https://schema.org',
    '@graph': [
      { '@type': 'WebSite', '@id': `${origin}/#website`, url: origin, name: 'MängelFix', inLanguage: ['de', 'en'] },
      { '@type': 'SoftwareApplication', '@id': `${origin}/#software`, name: 'MängelFix', applicationCategory: 'BusinessApplication', operatingSystem: 'Web, iOS', url: origin, offers: { '@type': 'Offer', price: '0', priceCurrency: 'EUR' }, publisher: { '@type': 'Organization', name: 'Kamilunavo', url: 'https://kamilunavo.com' } },
      { '@type': 'WebPage', '@id': `${canonical}#webpage`, url: canonical, name: title, description, inLanguage: locale, isPartOf: { '@id': `${origin}/#website` }, about: { '@id': `${origin}/#software` } }
    ]
  };
  const tags = [
    `<link rel="canonical" href="${clean(canonical)}">`,
    `<link rel="alternate" hreflang="de" href="${clean(absolute(dePath))}">`,
    `<link rel="alternate" hreflang="en" href="${clean(absolute(enPath))}">`,
    `<link rel="alternate" hreflang="x-default" href="${clean(absolute(dePath))}">`,
    `<meta property="og:type" content="website">`,
    `<meta property="og:site_name" content="MängelFix">`,
    `<meta property="og:locale" content="${locale === 'de' ? 'de_DE' : 'en_US'}">`,
    `<meta property="og:title" content="${clean(title)}">`,
    `<meta property="og:description" content="${clean(description)}">`,
    `<meta property="og:url" content="${clean(canonical)}">`,
    `<meta name="twitter:card" content="summary">`,
    `<script type="application/ld+json">${JSON.stringify(schema).replace(/</g, '\\u003c')}</script>`
  ].join('\n    ');
  return template
    .replace('<html lang="de">', `<html lang="${locale}">`)
    .replace(/<meta name="description" content="[^"]*" \/>/, `<meta name="description" content="${clean(description)}" />`)
    .replace(/<title>[^<]*<\/title>/, `<title>${clean(title)}</title>`)
    .replace('</head>', `    ${tags}\n  </head>`);
}
