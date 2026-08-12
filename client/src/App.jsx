import { useEffect, useMemo, useState } from 'react';

const statusLabels = {
  draft: 'Entwurf',
  sent: 'Versendet',
  reply: 'Rückmeldung',
  in_progress: 'In Bearbeitung',
  resolved: 'Erledigt'
};

const categories = ['Feuchtigkeit / Schimmel', 'Heizung / Warmwasser', 'Sanitär', 'Elektro', 'Fenster / Türen', 'Boden / Wand', 'Lärm', 'Außenbereich', 'Sonstiges'];

async function api(url, options = {}) {
  const response = await fetch(url, {
    credentials: 'same-origin',
    ...options,
    headers: options.body instanceof FormData ? options.headers : { 'Content-Type': 'application/json', ...(options.headers || {}) }
  });
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || 'Etwas ist schiefgelaufen.');
  return data;
}

function fmtDate(value) {
  if (!value) return '—';
  return new Intl.DateTimeFormat('de-DE').format(new Date(value));
}

function daysUntil(value) {
  if (!value) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(value);
  target.setHours(0, 0, 0, 0);
  return Math.ceil((target - today) / 86400000);
}

function usePath() {
  const [path, setPath] = useState(window.location.pathname);
  useEffect(() => {
    const listener = () => setPath(window.location.pathname);
    window.addEventListener('popstate', listener);
    return () => window.removeEventListener('popstate', listener);
  }, []);
  const navigate = next => {
    if (window.location.pathname !== next) window.history.pushState({}, '', next);
    setPath(next);
    window.scrollTo({ top: 0, behavior: 'instant' });
  };
  return [path, navigate];
}

function Logo({ inverse = false, compact = false }) {
  return (
    <div className={`mfLogo ${inverse ? 'inverse' : ''} ${compact ? 'compact' : ''}`}>
      <svg className="mfLogoMark" viewBox="0 0 52 52" aria-hidden="true">
        <rect x="2" y="2" width="48" height="48" rx="11" className="logoBase" />
        <path d="M15 12h17l7 7v21H15z" className="logoPaper" />
        <path d="M32 12v8h8" className="logoFold" />
        <path d="M20 29l4 4 9-11" className="logoCheck" />
      </svg>
      {!compact && <div className="mfLogoText"><strong>MängelFix</strong><span>Fälle sauber dokumentiert</span></div>}
    </div>
  );
}

function PublicHeader({ user, navigate }) {
  return (
    <header className="publicHeader">
      <button className="brandButton" onClick={() => navigate('/')}><Logo /></button>
      <nav className="publicNav">
        <a href="/#ablauf">So funktioniert's</a>
        <a href="/#funktionen">Funktionen</a>
        {user ? (
          <button className="navPrimary" onClick={() => navigate('/app')}>Zur App</button>
        ) : (
          <>
            <button className="navGhost" onClick={() => navigate('/anmelden')}>Anmelden</button>
            <button className="navPrimary" onClick={() => navigate('/registrieren')}>Kostenlos starten</button>
          </>
        )}
      </nav>
    </header>
  );
}

function PublicFooter({ navigate }) {
  return (
    <footer className="publicFooter">
      <div><Logo inverse /><p>Mängel dokumentieren, Fristen im Blick behalten und nachvollziehbare Unterlagen erstellen.</p></div>
      <div className="footerLinks">
        <button onClick={() => navigate('/impressum')}>Impressum</button>
        <button onClick={() => navigate('/datenschutz')}>Datenschutz</button>
        <button onClick={() => navigate('/nutzungsbedingungen')}>Nutzungsbedingungen</button>
      </div>
      <small>© 2026 Kamilunavo · MängelFix</small>
    </footer>
  );
}

function Landing({ user, navigate }) {
  return (
    <div className="landingPage">
      <PublicHeader user={user} navigate={navigate} />
      <main>
        <section className="landingHero">
          <div className="heroText">
            <div className="landingEyebrow"><span /> MÄNGEL FESTHALTEN, BEVOR DETAILS VERLOREN GEHEN</div>
            <h1>Aus einem Problem wird ein <em>sauber dokumentierter Vorgang.</em></h1>
            <p>Fotos, Beschreibung, Empfänger, Frist und Verlauf an einem Ort. MängelFix hilft dir, Mängel strukturiert festzuhalten und professionelle Unterlagen daraus zu erstellen.</p>
            <div className="heroActions">
              <button className="landingPrimary" onClick={() => navigate(user ? '/app' : '/registrieren')}>{user ? 'MängelFix öffnen' : 'Kostenlos starten'} <span>→</span></button>
              <a className="landingSecondary" href="#ablauf">So funktioniert's</a>
            </div>
            <div className="heroTrust"><span>✓</span> Keine Zettelwirtschaft <span>✓</span> PDF-Dokumentation <span>✓</span> Fristen & Verlauf</div>
          </div>
          <div className="heroVisual" aria-label="Vorschau einer MängelFix-Dokumentation">
            <div className="visualBack visualBackOne" />
            <div className="visualBack visualBackTwo" />
            <div className="documentPreview">
              <div className="docTop"><Logo compact inverse /><div><small>VORGANG</small><b>A14F39C2</b></div></div>
              <div className="docBody">
                <small>MÄNGELANZEIGE</small>
                <h3>Heizung bleibt kalt</h3>
                <div className="docStatus">IN BEARBEITUNG</div>
                <div className="docFacts"><span><small>Objekt</small><b>Wohnung Musterstraße</b></span><span><small>Frist</small><b>15.08.2026</b></span></div>
                <div className="docLine" /><div className="docLine medium" /><div className="docLine short" />
                <div className="docPhotoRow"><div /><div /></div>
              </div>
            </div>
            <div className="floatingBadge"><b>PDF</b><span>Professionell vorbereitet</span></div>
          </div>
        </section>

        <section className="problemStrip">
          <div><strong>Ein Mangel.</strong><span>Nicht fünf Chats, drei Fotosammlungen und ein vergessener Zettel.</span></div>
          <div className="stripRule" />
          <div><strong>Ein Vorgang.</strong><span>Alles nachvollziehbar an einer Stelle.</span></div>
        </section>

        <section className="landingSection" id="ablauf">
          <div className="sectionIntro"><span>SO FUNKTIONIERT MÄNGELFIX</span><h2>Von der Feststellung bis zur Erledigung.</h2><p>Ein klarer Ablauf, ohne dass du dir jedes Detail selbst zusammensuchen musst.</p></div>
          <div className="stepRail">
            <article><b>01</b><h3>Mangel erfassen</h3><p>Was ist passiert, wo ist es passiert und wann wurde es festgestellt?</p></article>
            <article><b>02</b><h3>Belege ergänzen</h3><p>Fotos, Empfänger und gewünschte Rückmeldefrist direkt dem Fall zuordnen.</p></article>
            <article><b>03</b><h3>Dokument erstellen</h3><p>Aus deinen Angaben entsteht eine übersichtliche Mängelanzeige inklusive Absender.</p></article>
            <article><b>04</b><h3>Verlauf nachhalten</h3><p>Status, Antworten und eigene Notizen bleiben chronologisch nachvollziehbar.</p></article>
          </div>
        </section>

        <section className="featureSection" id="funktionen">
          <div className="featureHeading"><span>DEIN DIGITALER MÄNGELORDNER</span><h2>Gebaut für echte Vorgänge, nicht für hübsche Demo-Karten.</h2></div>
          <div className="featureGrid">
            <article className="featureLarge"><div className="featureNumber">01</div><h3>Alle Fälle im Blick</h3><p>Offen, versendet, in Bearbeitung oder erledigt. Du siehst sofort, wo etwas noch Aufmerksamkeit braucht.</p><div className="miniCaseList"><span><i className="dot amber" />Heizung bleibt kalt <b>OFFEN</b></span><span><i className="dot blue" />Fenster undicht <b>VERSENDET</b></span><span><i className="dot green" />Armatur defekt <b>ERLEDIGT</b></span></div></article>
            <article><div className="featureNumber">02</div><h3>Fristen</h3><p>Rückmeldedaten werden separat sichtbar, damit offene Termine nicht untergehen.</p></article>
            <article><div className="featureNumber">03</div><h3>Fotobelege</h3><p>Bilder bleiben direkt am jeweiligen Mangel und können in die Dokumentation übernommen werden.</p></article>
            <article><div className="featureNumber">04</div><h3>Absenderprofil</h3><p>Name und Anschrift einmal hinterlegen und automatisch in deinen PDFs verwenden.</p></article>
            <article><div className="featureNumber">05</div><h3>Vorgangsverlauf</h3><p>Notizen und Statusänderungen bilden eine nachvollziehbare Historie des Falls.</p></article>
          </div>
        </section>

        <section className="landingCta">
          <div><span>BEREIT FÜR DEN ERSTEN VORGANG?</span><h2>Dokumentiere lieber einmal sauber als später aus dem Gedächtnis.</h2></div>
          <button onClick={() => navigate(user ? '/app' : '/registrieren')}>{user ? 'Zur App' : 'MängelFix kostenlos starten'} →</button>
        </section>
      </main>
      <PublicFooter navigate={navigate} />
    </div>
  );
}

function Auth({ mode, onSignedIn, navigate }) {
  const [form, setForm] = useState({ name: '', email: '', password: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const register = mode === 'register';

  async function submit(event) {
    event.preventDefault();
    setBusy(true); setError('');
    try {
      const data = await api(register ? '/api/auth/register' : '/api/auth/login', { method: 'POST', body: JSON.stringify(form) });
      onSignedIn(data.user);
      navigate('/app');
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return (
    <div className="authStandalone">
      <PublicHeader navigate={navigate} />
      <main className="authStage">
        <section className="authPitch">
          <div className="landingEyebrow"><span /> MÄNGELFIX KONTO</div>
          <h1>{register ? 'Deine Mängel. Ein Ort. Ein sauberer Verlauf.' : 'Willkommen zurück.'}</h1>
          <p>{register ? 'Starte mit deinem persönlichen Mängelordner und ergänze dein Absenderprofil anschließend in wenigen Sekunden.' : 'Öffne deine Vorgänge, Fristen und Dokumente.'}</p>
          <div className="authBenefits"><span>✓ Fälle & Fotos zentral gespeichert</span><span>✓ Professionelle PDF-Dokumentation</span><span>✓ Fristen und Verlauf im Blick</span></div>
        </section>
        <section className="authBox">
          <div className="authBoxHead"><span>{register ? 'KONTO ERSTELLEN' : 'ANMELDEN'}</span><h2>{register ? 'MängelFix starten' : 'In dein Konto'}</h2></div>
          <form onSubmit={submit} className="formStack">
            {register && <label>Name<input required value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} autoComplete="name" placeholder="Vor- und Nachname" /></label>}
            <label>E-Mail<input required type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} autoComplete="email" placeholder="name@beispiel.de" /></label>
            <label>Passwort<input required minLength="8" type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} autoComplete={register ? 'new-password' : 'current-password'} placeholder="Mindestens 8 Zeichen" /></label>
            {error && <div className="errorBox">{error}</div>}
            <button className="primaryButton authSubmit" disabled={busy}>{busy ? 'Einen Moment…' : register ? 'Konto erstellen' : 'Anmelden'}</button>
          </form>
          <div className="authSwitch">{register ? 'Du hast bereits ein Konto?' : 'Noch kein MängelFix-Konto?'} <button onClick={() => navigate(register ? '/anmelden' : '/registrieren')}>{register ? 'Anmelden' : 'Kostenlos registrieren'}</button></div>
          <p className="legalHint">Mit der Nutzung gelten unsere <button onClick={() => navigate('/nutzungsbedingungen')}>Nutzungsbedingungen</button> und <button onClick={() => navigate('/datenschutz')}>Datenschutzhinweise</button>.</p>
        </section>
      </main>
      <PublicFooter navigate={navigate} />
    </div>
  );
}

function LegalPage({ type, navigate }) {
  const content = {
    impressum: {
      eyebrow: 'RECHTLICHE ANGABEN',
      title: 'Impressum',
      sections: [
        ['Angaben gemäß § 5 DDG', <><p><b>Kamilunavo</b><br />Inhaber: Piotr Kaminski<br />Otto-Braun-Straße 14<br />40595 Düsseldorf<br />Deutschland</p><p>„Kamilunavo“ ist die verwendete Geschäftsbezeichnung. Diensteanbieter und verantwortlich für MängelFix ist die oben genannte natürliche Person.</p></>],
        ['Kontakt', <p>E-Mail: <a href="mailto:contact@kamilunavo.com">contact@kamilunavo.com</a></p>],
        ['Verantwortlich für Inhalte', <p>Piotr Kaminski, Anschrift wie oben.</p>],
        ['Verbraucherstreitbeilegung', <p>Wir sind nicht verpflichtet und derzeit nicht bereit, an einem Streitbeilegungsverfahren vor einer Verbraucherschlichtungsstelle teilzunehmen.</p>],
        ['Hinweis zum Angebot', <p>MängelFix unterstützt bei Dokumentation und Organisation von Mängeln. Das Angebot ersetzt keine individuelle Rechtsberatung und trifft keine verbindliche rechtliche Bewertung eines Falls.</p>]
      ]
    },
    datenschutz: {
      eyebrow: 'DATENSCHUTZ',
      title: 'Datenschutzerklärung',
      sections: [
        ['1. Verantwortlicher', <p>Kamilunavo · Inhaber Piotr Kaminski<br />Otto-Braun-Straße 14, 40595 Düsseldorf, Deutschland<br />E-Mail: <a href="mailto:contact@kamilunavo.com">contact@kamilunavo.com</a></p>],
        ['2. Welche Daten MängelFix verarbeitet', <p>Bei der Nutzung verarbeiten wir insbesondere Kontodaten wie Name und E-Mail-Adresse, freiwillige Profildaten wie Anschrift und Telefonnummer, die von dir erfassten Mängeldaten, Empfängerdaten, Fristen, Notizen sowie hochgeladene Fotos und technische Sitzungsdaten.</p>],
        ['3. Zweck und Rechtsgrundlage', <p>Die Daten werden verarbeitet, um dein Konto bereitzustellen, deine Vorgänge zu speichern, Dokumente zu erzeugen, Fotos zuzuordnen und die Anmeldung abzusichern. Soweit die Verarbeitung für die Bereitstellung des Dienstes erforderlich ist, erfolgt sie zur Durchführung des Nutzungsverhältnisses. Technisch erforderliche Sicherheitsmaßnahmen dienen außerdem dem sicheren und stabilen Betrieb.</p>],
        ['4. Empfängerdaten und Inhalte Dritter', <p>Wenn du Daten von Vermietern, Hausverwaltungen, Handwerksbetrieben oder anderen Personen einträgst oder Fotos hochlädst, entscheidest du über diese Inhalte. Bitte erfasse nur Daten, die für die Dokumentation deines Vorgangs erforderlich sind.</p>],
        ['5. Hosting', <p>MängelFix wird auf Serverinfrastruktur in Deutschland betrieben. Als Hosting-Dienstleister wird Hetzner Online GmbH eingesetzt. Dabei können technisch notwendige Verbindungs- und Serverdaten verarbeitet werden.</p>],
        ['6. Cookies und Anmeldung', <p>MängelFix verwendet ein technisch erforderliches Session-Cookie, damit du angemeldet bleibst. Es wird derzeit nicht für Werbung, Profilbildung oder Tracking verwendet.</p>],
        ['7. Speicherdauer', <p>Kontodaten und von dir angelegte Vorgänge werden grundsätzlich gespeichert, solange dein Konto besteht oder die Daten für die Bereitstellung des Dienstes benötigt werden. Löschanfragen kannst du an contact@kamilunavo.com richten, soweit keine gesetzlichen Aufbewahrungspflichten entgegenstehen.</p>],
        ['8. Deine Rechte', <p>Nach den anwendbaren Datenschutzvorschriften können dir insbesondere Rechte auf Auskunft, Berichtigung, Löschung, Einschränkung der Verarbeitung, Datenübertragbarkeit und Widerspruch zustehen. Außerdem besteht ein Beschwerderecht bei einer zuständigen Datenschutzaufsichtsbehörde.</p>],
        ['9. Sicherheit', <p>Wir setzen technische und organisatorische Maßnahmen ein, um personenbezogene Daten gegen unbefugten Zugriff, Verlust und Missbrauch zu schützen. Passwörter werden nicht im Klartext gespeichert.</p>],
        ['10. Stand', <p>Stand: 12. August 2026. Diese Datenschutzerklärung wird angepasst, wenn sich Funktionen oder Datenverarbeitungen von MängelFix ändern.</p>]
      ]
    },
    terms: {
      eyebrow: 'NUTZUNGSBEDINGUNGEN',
      title: 'Nutzungsbedingungen',
      sections: [
        ['1. Geltungsbereich', <p>Diese Nutzungsbedingungen gelten für die Nutzung von MängelFix, einem Dienst von Kamilunavo, Inhaber Piotr Kaminski.</p>],
        ['2. Leistungsumfang', <p>MängelFix unterstützt Nutzer beim Erfassen, Dokumentieren und Organisieren von Mängeln sowie beim Erstellen von PDF-Unterlagen. MängelFix ist kein Rechtsberatungsdienst und ersetzt keine individuelle rechtliche Prüfung.</p>],
        ['3. Benutzerkonto', <p>Für den geschützten App-Bereich ist ein Benutzerkonto erforderlich. Zugangsdaten sind vertraulich zu behandeln. Angaben im Konto und in erzeugten Dokumenten sollen aktuell und sachlich richtig gehalten werden.</p>],
        ['4. Eigene Inhalte', <p>Nutzer sind für eingegebene Texte, Empfängerdaten und hochgeladene Bilder verantwortlich. Es dürfen keine rechtswidrigen Inhalte hochgeladen oder Rechte Dritter verletzt werden.</p>],
        ['5. Verfügbarkeit und Änderungen', <p>Wir entwickeln MängelFix fortlaufend weiter. Funktionen können ergänzt, angepasst oder aus technischen Gründen vorübergehend eingeschränkt werden.</p>],
        ['6. Dokumente', <p>Von MängelFix erzeugte PDFs beruhen auf den vom Nutzer eingegebenen Angaben. Vor dem Versand oder der Verwendung eines Dokuments sollte der Inhalt auf Vollständigkeit und Richtigkeit geprüft werden.</p>],
        ['7. Kontakt', <p>Fragen zu MängelFix oder diesen Bedingungen: <a href="mailto:contact@kamilunavo.com">contact@kamilunavo.com</a>.</p>],
        ['8. Stand', <p>Stand: 12. August 2026.</p>]
      ]
    }
  }[type];

  return (
    <div className="legalPage">
      <PublicHeader navigate={navigate} />
      <main className="legalWrap">
        <button className="legalBack" onClick={() => navigate('/')}>← Zur Startseite</button>
        <div className="legalHeading"><span>{content.eyebrow}</span><h1>{content.title}</h1></div>
        <div className="legalDocument">{content.sections.map(([heading, body]) => <section key={heading}><h2>{heading}</h2>{body}</section>)}</div>
      </main>
      <PublicFooter navigate={navigate} />
    </div>
  );
}

function NewCase({ onClose, onCreated }) {
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({ title: '', category: categories[0], description: '', propertyLabel: '', locationLabel: '', discoveredOn: today, recipientName: '', recipientEmail: '', recipientAddress: '', deadlineOn: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const field = (name, value) => setForm(current => ({ ...current, [name]: value }));

  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const data = await api('/api/cases', { method: 'POST', body: JSON.stringify(form) });
      onCreated(data.case);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return (
    <div className="modalBackdrop" onMouseDown={onClose}>
      <div className="modal proModal" onMouseDown={e => e.stopPropagation()}>
        <div className="modalHeader"><div><div className="eyebrow">NEUER VORGANG</div><h2>Mangel erfassen</h2></div><button className="iconButton" onClick={onClose}>×</button></div>
        <form onSubmit={submit} className="caseForm">
          <div className="formGrid two"><label>Titel<input required placeholder="z. B. Heizung bleibt kalt" value={form.title} onChange={e => field('title', e.target.value)} /></label><label>Kategorie<select value={form.category} onChange={e => field('category', e.target.value)}>{categories.map(item => <option key={item}>{item}</option>)}</select></label></div>
          <label>Beschreibung<textarea required rows="5" placeholder="Beschreibe den Mangel so konkret wie möglich…" value={form.description} onChange={e => field('description', e.target.value)} /></label>
          <div className="formGrid two"><label>Objekt<input placeholder="z. B. Wohnung, Musterstraße 12" value={form.propertyLabel} onChange={e => field('propertyLabel', e.target.value)} /></label><label>Raum / Ort<input placeholder="z. B. Badezimmer" value={form.locationLabel} onChange={e => field('locationLabel', e.target.value)} /></label><label>Festgestellt am<input type="date" value={form.discoveredOn} onChange={e => field('discoveredOn', e.target.value)} /></label><label>Rückmeldung bis<input type="date" value={form.deadlineOn} onChange={e => field('deadlineOn', e.target.value)} /></label></div>
          <div className="subSection"><h3>Empfänger</h3><p className="muted">Optional – Hausverwaltung, Vermieter oder anderer Ansprechpartner.</p></div>
          <div className="formGrid two"><label>Name / Firma<input value={form.recipientName} onChange={e => field('recipientName', e.target.value)} /></label><label>E-Mail<input type="email" value={form.recipientEmail} onChange={e => field('recipientEmail', e.target.value)} /></label></div>
          <label>Anschrift<textarea rows="2" placeholder="Straße, Hausnummer, PLZ Ort" value={form.recipientAddress} onChange={e => field('recipientAddress', e.target.value)} /></label>
          {error && <div className="errorBox">{error}</div>}
          <div className="modalActions"><button type="button" className="secondaryButton" onClick={onClose}>Abbrechen</button><button className="primaryButton" disabled={busy}>{busy ? 'Speichern…' : 'Vorgang anlegen'}</button></div>
        </form>
      </div>
    </div>
  );
}

function CaseDetail({ caseId, onBack, onUpdated, user, onProfile }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const profileComplete = Boolean(user.street && user.postalCode && user.city);

  async function load() {
    try { setData(await api(`/api/cases/${caseId}`)); }
    catch (err) { setError(err.message); }
  }
  useEffect(() => { load(); }, [caseId]);

  async function changeStatus(status) {
    setBusy(true); setError('');
    try { await api(`/api/cases/${caseId}`, { method: 'PATCH', body: JSON.stringify({ status }) }); await load(); onUpdated(); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function addNote(event) {
    event.preventDefault(); if (!note.trim()) return;
    setBusy(true);
    try { await api(`/api/cases/${caseId}/events`, { method: 'POST', body: JSON.stringify({ note }) }); setNote(''); await load(); onUpdated(); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function uploadImages(event) {
    const files = [...event.target.files];
    if (!files.length) return;
    const form = new FormData(); files.forEach(file => form.append('images', file));
    setBusy(true);
    try { await api(`/api/cases/${caseId}/attachments`, { method: 'POST', body: form }); await load(); onUpdated(); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); event.target.value = ''; }
  }

  if (!data) return <div className="workspacePage"><button className="backButton" onClick={onBack}>← Zurück</button><div className="emptyCard">{error || 'Vorgang wird geladen…'}</div></div>;
  const item = data.case;

  return (
    <div className="workspacePage detailPage">
      <button className="backButton" onClick={onBack}>← Alle Mängel</button>
      <div className="detailHeader">
        <div><div className="eyebrow">{item.category}</div><h1>{item.title}</h1><div className="metaLine"><span className={`status status-${item.status}`}>{statusLabels[item.status]}</span><span>Festgestellt: {fmtDate(item.discovered_on)}</span><span>Vorgang {item.id.split('-')[0].toUpperCase()}</span></div></div>
        <div className="detailActions">{!profileComplete && <button className="profileWarning" onClick={onProfile}>Absender ergänzen</button>}<a className="primaryButton linkButton" href={`/api/cases/${item.id}/pdf`} target="_blank" rel="noreferrer">PDF erstellen</a></div>
      </div>
      {!profileComplete && <div className="noticeBar"><b>Absenderprofil unvollständig.</b> Ergänze Straße, PLZ und Ort, damit deine Mängelanzeige einen vollständigen Absender enthält. <button onClick={onProfile}>Jetzt ergänzen</button></div>}
      {error && <div className="errorBox">{error}</div>}
      <div className="detailGrid">
        <section className="contentCard"><div className="cardKicker">FALLINHALT</div><h3>Beschreibung</h3><p className="descriptionText">{item.description}</p><div className="factsGrid"><div><span>Objekt</span><b>{item.property_label || '—'}</b></div><div><span>Raum / Ort</span><b>{item.location_label || '—'}</b></div><div><span>Rückmeldung bis</span><b>{fmtDate(item.deadline_on)}</b></div><div><span>Empfänger</span><b>{item.recipient_name || 'Noch nicht hinterlegt'}</b></div></div></section>
        <aside className="contentCard actionCard"><div className="cardKicker">VORGANG</div><h3>Status</h3><select disabled={busy} value={item.status} onChange={e => changeStatus(e.target.value)}>{Object.entries(statusLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select><p className="muted small">Statusänderungen werden automatisch im Verlauf protokolliert.</p><div className="sideInfo"><span>Fotobelege<b>{data.attachments.length}</b></span><span>Frist<b>{fmtDate(item.deadline_on)}</b></span></div></aside>
      </div>
      <section className="contentCard"><div className="sectionTitle"><div><div className="cardKicker">BEWEISSICHERUNG</div><h3>Fotos & Belege</h3><p className="muted">Bis zu 5 Bilder pro Upload, jeweils maximal 10 MB.</p></div><label className="secondaryButton uploadButton">Bilder hinzufügen<input type="file" accept="image/*" multiple onChange={uploadImages} /></label></div>{data.attachments.length ? <div className="photoGrid">{data.attachments.map(file => <a key={file.id} href={`/api/attachments/${file.id}`} target="_blank" rel="noreferrer"><img src={`/api/attachments/${file.id}`} alt={file.original_name} /><span>{file.original_name}</span></a>)}</div> : <div className="emptyInline">Noch keine Bilder hinterlegt.</div>}</section>
      <section className="contentCard"><div className="sectionTitle"><div><div className="cardKicker">CHRONOLOGIE</div><h3>Verlauf</h3><p className="muted">Notizen und Statusänderungen bleiben nachvollziehbar.</p></div></div><form className="noteForm" onSubmit={addNote}><input placeholder="Neue Notiz, z. B. Hausverwaltung telefonisch erreicht…" value={note} onChange={e => setNote(e.target.value)} /><button className="primaryButton" disabled={busy}>Notiz speichern</button></form><div className="timeline">{data.events.map(event => <div className="timelineItem" key={event.id}><div className="timelineDot"/><div><b>{event.event_type === 'created' ? 'Fall erstellt' : event.event_type === 'status' ? 'Status geändert' : 'Notiz'}</b><p>{event.note}</p><span>{new Date(event.created_at).toLocaleString('de-DE')}</span></div></div>)}</div></section>
    </div>
  );
}

function CaseRows({ cases, onSelect, emptyText = 'Keine Vorgänge vorhanden.' }) {
  if (!cases.length) return <div className="emptyCard workspaceEmpty">{emptyText}</div>;
  return <div className="workspaceTable">{cases.map(item => <button key={item.id} className="tableRow" onClick={() => onSelect(item.id)}><div className="rowAlert">!</div><div className="rowMain"><div><h3>{item.title}</h3><span className={`status status-${item.status}`}>{statusLabels[item.status]}</span></div><p>{item.property_label || item.location_label || item.category}</p></div><div className="rowMeta"><span>{item.category}</span><span>{item.attachment_count} Bild{item.attachment_count === 1 ? '' : 'er'}</span></div><div className="rowDeadline">{item.deadline_on ? <><small>Frist</small><b>{fmtDate(item.deadline_on)}</b></> : <span>Keine Frist</span>}</div><span className="rowArrow">→</span></button>)}</div>;
}

function OverviewView({ user, cases, onNew, onSelect, setView }) {
  const counts = useMemo(() => ({
    open: cases.filter(item => item.status !== 'resolved').length,
    resolved: cases.filter(item => item.status === 'resolved').length,
    deadlines: cases.filter(item => item.deadline_on && item.status !== 'resolved').length
  }), [cases]);
  const urgent = cases.filter(item => item.deadline_on && item.status !== 'resolved').sort((a, b) => new Date(a.deadline_on) - new Date(b.deadline_on)).slice(0, 3);
  return <div className="workspacePage"><div className="workspaceHeading"><div><span>ÜBERSICHT</span><h1>Guten Abend, {user.name.split(' ')[0]}.</h1><p>Hier siehst du, welche Vorgänge gerade Aufmerksamkeit brauchen.</p></div><button className="workspacePrimary" onClick={onNew}>+ Mangel erfassen</button></div><div className="metricGrid"><button onClick={() => setView('cases')}><span>OFFENE VORGÄNGE</span><strong>{counts.open}</strong><small>Noch nicht abgeschlossen</small></button><button onClick={() => setView('deadlines')}><span>AKTIVE FRISTEN</span><strong>{counts.deadlines}</strong><small>Mit Rückmeldedatum</small></button><button onClick={() => setView('documents')}><span>DOKUMENTE</span><strong>{cases.length}</strong><small>PDF-fähige Vorgänge</small></button><button onClick={() => setView('cases')}><span>ERLEDIGT</span><strong>{counts.resolved}</strong><small>Abgeschlossene Fälle</small></button></div><div className="dashboardColumns"><section className="workspacePanel"><div className="panelHead"><div><span>LETZTE VORGÄNGE</span><h2>Zuletzt bearbeitet</h2></div><button onClick={() => setView('cases')}>Alle anzeigen →</button></div><CaseRows cases={cases.slice(0, 5)} onSelect={onSelect} emptyText="Noch kein Mangel erfasst." /></section><aside className="workspacePanel deadlinePanel"><div className="panelHead"><div><span>FRISTEN</span><h2>Als Nächstes</h2></div></div>{urgent.length ? urgent.map(item => { const d = daysUntil(item.deadline_on); return <button key={item.id} className={`deadlineItem ${d < 0 ? 'overdue' : d <= 3 ? 'soon' : ''}`} onClick={() => onSelect(item.id)}><div><b>{item.title}</b><span>{item.property_label || item.category}</span></div><strong>{d < 0 ? `${Math.abs(d)} T. überfällig` : d === 0 ? 'Heute' : `${d} Tage`}</strong></button>; }) : <div className="emptyMini">Keine offenen Fristen.</div>}</aside></div></div>;
}

function CasesView({ cases, onNew, onSelect }) {
  const [filter, setFilter] = useState('all');
  const filtered = filter === 'all' ? cases : filter === 'open' ? cases.filter(x => x.status !== 'resolved') : cases.filter(x => x.status === 'resolved');
  return <div className="workspacePage"><div className="workspaceHeading"><div><span>MÄNGEL</span><h1>Alle Vorgänge</h1><p>Dokumentierte Mängel mit Status, Fristen und Belegen.</p></div><button className="workspacePrimary" onClick={onNew}>+ Mangel erfassen</button></div><div className="filterBar"><button className={filter === 'all' ? 'active' : ''} onClick={() => setFilter('all')}>Alle <b>{cases.length}</b></button><button className={filter === 'open' ? 'active' : ''} onClick={() => setFilter('open')}>Offen <b>{cases.filter(x => x.status !== 'resolved').length}</b></button><button className={filter === 'done' ? 'active' : ''} onClick={() => setFilter('done')}>Erledigt <b>{cases.filter(x => x.status === 'resolved').length}</b></button></div><CaseRows cases={filtered} onSelect={onSelect} /></div>;
}

function ObjectsView({ cases, onSelect }) {
  const groups = useMemo(() => {
    const map = new Map();
    cases.forEach(item => {
      const key = item.property_label || 'Ohne Objektzuordnung';
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(item);
    });
    return [...map.entries()];
  }, [cases]);
  return <div className="workspacePage"><div className="workspaceHeading"><div><span>OBJEKTE</span><h1>Objekte & Wohnungen</h1><p>Automatisch aus deinen Vorgängen gruppiert.</p></div></div><div className="objectGrid">{groups.length ? groups.map(([name, items]) => <article className="objectCard" key={name}><div className="objectIcon">⌂</div><div><span>OBJEKT</span><h2>{name}</h2><p>{items.length} Vorgang{items.length === 1 ? '' : 'e'} · {items.filter(x => x.status !== 'resolved').length} offen</p></div><div className="objectCases">{items.slice(0, 3).map(item => <button key={item.id} onClick={() => onSelect(item.id)}><span className={`tinyStatus status-${item.status}`} />{item.title}<b>→</b></button>)}</div></article>) : <div className="emptyCard workspaceEmpty">Sobald du bei einem Mangel ein Objekt angibst, erscheint es hier.</div>}</div></div>;
}

function DeadlinesView({ cases, onSelect }) {
  const deadlines = cases.filter(x => x.deadline_on && x.status !== 'resolved').sort((a, b) => new Date(a.deadline_on) - new Date(b.deadline_on));
  return <div className="workspacePage"><div className="workspaceHeading"><div><span>FRISTEN</span><h1>Offene Rückmeldetermine</h1><p>Sortiert nach dem nächsten fälligen Datum.</p></div></div><div className="deadlineList">{deadlines.length ? deadlines.map(item => { const d = daysUntil(item.deadline_on); return <button key={item.id} className={`deadlineRow ${d < 0 ? 'overdue' : d <= 3 ? 'soon' : ''}`} onClick={() => onSelect(item.id)}><div className="dateBlock"><b>{new Date(item.deadline_on).toLocaleDateString('de-DE', { day: '2-digit' })}</b><span>{new Date(item.deadline_on).toLocaleDateString('de-DE', { month: 'short' }).toUpperCase()}</span></div><div><h3>{item.title}</h3><p>{item.property_label || item.category}</p></div><span className={`status status-${item.status}`}>{statusLabels[item.status]}</span><strong>{d < 0 ? `${Math.abs(d)} Tage überfällig` : d === 0 ? 'Heute fällig' : `in ${d} Tagen`}</strong><span>→</span></button>; }) : <div className="emptyCard workspaceEmpty">Keine offenen Fristen. Bei neuen Vorgängen kannst du ein gewünschtes Rückmeldedatum setzen.</div>}</div></div>;
}

function DocumentsView({ cases, profileComplete, onProfile }) {
  return <div className="workspacePage"><div className="workspaceHeading"><div><span>DOKUMENTE</span><h1>PDF-Dokumentation</h1><p>Erzeuge aus jedem Vorgang eine sauber aufgebaute Mängelanzeige.</p></div></div>{!profileComplete && <div className="noticeBar"><b>Für vollständige Dokumente fehlt noch deine Anschrift.</b> <button onClick={onProfile}>Absenderprofil vervollständigen</button></div>}<div className="documentList">{cases.length ? cases.map(item => <article key={item.id} className="documentRow"><div className="pdfIcon">PDF</div><div><h3>{item.title}</h3><p>Vorgang {item.id.split('-')[0].toUpperCase()} · {item.property_label || item.category}</p></div><span className={`status status-${item.status}`}>{statusLabels[item.status]}</span><a href={`/api/cases/${item.id}/pdf`} target="_blank" rel="noreferrer">PDF erstellen →</a></article>) : <div className="emptyCard workspaceEmpty">Noch keine Vorgänge vorhanden.</div>}</div></div>;
}

function ProfileView({ user, onSaved }) {
  const [form, setForm] = useState({ name: user.name || '', street: user.street || '', postalCode: user.postalCode || '', city: user.city || '', country: user.country || 'Deutschland', phone: user.phone || '' });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const field = (name, value) => setForm(current => ({ ...current, [name]: value }));
  async function save(event) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('');
    try { const data = await api('/api/profile', { method: 'PATCH', body: JSON.stringify(form) }); onSaved(data.user); setMessage('Absenderprofil gespeichert. Neue PDFs verwenden diese Angaben automatisch.'); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <div className="workspacePage"><div className="workspaceHeading"><div><span>PROFIL</span><h1>Absender & Konto</h1><p>Diese Angaben erscheinen als Absender in deiner MängelFix-PDF.</p></div></div><div className="profileLayout"><form className="workspacePanel profileForm" onSubmit={save}><div className="panelHead"><div><span>ABSENDERDATEN</span><h2>Deine Kontaktdaten</h2></div></div><div className="formGrid two"><label>Name<input required value={form.name} onChange={e => field('name', e.target.value)} /></label><label>E-Mail<input disabled value={user.email} /></label><label>Straße & Hausnummer<input required placeholder="Musterstraße 12" value={form.street} onChange={e => field('street', e.target.value)} /></label><label>Telefon <em>optional</em><input placeholder="+49 …" value={form.phone} onChange={e => field('phone', e.target.value)} /></label><label>PLZ<input required value={form.postalCode} onChange={e => field('postalCode', e.target.value)} /></label><label>Ort<input required value={form.city} onChange={e => field('city', e.target.value)} /></label></div><label>Land<input value={form.country} onChange={e => field('country', e.target.value)} /></label>{error && <div className="errorBox">{error}</div>}{message && <div className="successBox">{message}</div>}<div className="profileActions"><button className="primaryButton" disabled={busy}>{busy ? 'Speichern…' : 'Profil speichern'}</button></div></form><aside className="senderPreview"><span>PDF-VORSCHAU</span><h3>Absender</h3><p><b>{form.name || 'Dein Name'}</b><br />{form.street || 'Straße & Hausnummer'}<br />{form.postalCode || 'PLZ'} {form.city || 'Ort'}<br />{form.country || 'Deutschland'}<br />{user.email}{form.phone ? <><br />{form.phone}</> : null}</p><small>Diese Angaben werden nicht öffentlich angezeigt. Sie werden für dein Konto und die von dir erzeugten Dokumente verwendet.</small></aside></div></div>;
}

function Workspace({ user, setUser, onLogout, navigate }) {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showNew, setShowNew] = useState(false);
  const [selected, setSelected] = useState(null);
  const [view, setView] = useState('overview');

  async function loadCases() {
    try { const data = await api('/api/cases'); setCases(data.cases); setError(''); }
    catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }
  useEffect(() => { loadCases(); }, []);
  const profileComplete = Boolean(user.street && user.postalCode && user.city);
  const goProfile = () => { setSelected(null); setView('profile'); };

  let content;
  if (selected) content = <CaseDetail caseId={selected} onBack={() => setSelected(null)} onUpdated={loadCases} user={user} onProfile={goProfile} />;
  else if (loading) content = <div className="workspacePage"><div className="emptyCard">Vorgänge werden geladen…</div></div>;
  else if (view === 'overview') content = <OverviewView user={user} cases={cases} onNew={() => setShowNew(true)} onSelect={setSelected} setView={setView} />;
  else if (view === 'cases') content = <CasesView cases={cases} onNew={() => setShowNew(true)} onSelect={setSelected} />;
  else if (view === 'objects') content = <ObjectsView cases={cases} onSelect={setSelected} />;
  else if (view === 'deadlines') content = <DeadlinesView cases={cases} onSelect={setSelected} />;
  else if (view === 'documents') content = <DocumentsView cases={cases} profileComplete={profileComplete} onProfile={goProfile} />;
  else content = <ProfileView user={user} onSaved={setUser} />;

  return <div className="workspaceShell"><aside className="workspaceSidebar"><button className="sidebarBrand" onClick={() => setView('overview')}><Logo inverse /></button><div className="sidebarLabel">ARBEITSBEREICH</div><nav><button className={view === 'overview' && !selected ? 'active' : ''} onClick={() => { setSelected(null); setView('overview'); }}><span>Ü</span>Übersicht</button><button className={view === 'cases' || selected ? 'active' : ''} onClick={() => { setSelected(null); setView('cases'); }}><span>M</span>Mängel <b>{cases.filter(x => x.status !== 'resolved').length}</b></button><button className={view === 'objects' ? 'active' : ''} onClick={() => { setSelected(null); setView('objects'); }}><span>O</span>Objekte</button><button className={view === 'deadlines' ? 'active' : ''} onClick={() => { setSelected(null); setView('deadlines'); }}><span>F</span>Fristen <b>{cases.filter(x => x.deadline_on && x.status !== 'resolved').length}</b></button><button className={view === 'documents' ? 'active' : ''} onClick={() => { setSelected(null); setView('documents'); }}><span>D</span>Dokumente</button></nav><div className="sidebarBottom"><button className={view === 'profile' ? 'active' : ''} onClick={goProfile}><span>P</span>Profil {!profileComplete && <i />}</button><button onClick={() => navigate('/')}><span>↗</span>Startseite</button><div className="sidebarUser"><div>{user.name.slice(0, 1).toUpperCase()}</div><p><b>{user.name}</b><span>{user.email}</span></p><button onClick={onLogout} title="Abmelden">↪</button></div></div></aside><main className="workspaceMain"><div className="mobileWorkspaceBar"><Logo compact /><button onClick={() => setShowNew(true)}>+ Neuer Mangel</button></div>{error && <div className="workspaceGlobalError">{error}</div>}{content}</main>{showNew && <NewCase onClose={() => setShowNew(false)} onCreated={created => { setShowNew(false); loadCases(); setSelected(created.id); }} />}</div>;
}

export default function App() {
  const [path, navigate] = usePath();
  const [state, setState] = useState({ loading: true, user: null });

  useEffect(() => {
    api('/api/me').then(data => setState({ loading: false, user: data.user })).catch(() => setState({ loading: false, user: null }));
  }, []);

  async function logout() {
    try { await api('/api/auth/logout', { method: 'POST' }); } catch { /* session may already be gone */ }
    setState({ loading: false, user: null });
    navigate('/');
  }

  if (state.loading) return <div className="brandSplash"><Logo /><div className="loader" /></div>;
  if (path === '/impressum') return <LegalPage type="impressum" navigate={navigate} />;
  if (path === '/datenschutz') return <LegalPage type="datenschutz" navigate={navigate} />;
  if (path === '/nutzungsbedingungen') return <LegalPage type="terms" navigate={navigate} />;
  if (path === '/anmelden') return <Auth mode="login" onSignedIn={user => setState({ loading: false, user })} navigate={navigate} />;
  if (path === '/registrieren') return <Auth mode="register" onSignedIn={user => setState({ loading: false, user })} navigate={navigate} />;
  if (path.startsWith('/app')) {
    if (!state.user) return <Auth mode="login" onSignedIn={user => setState({ loading: false, user })} navigate={navigate} />;
    return <Workspace user={state.user} setUser={user => setState({ loading: false, user })} onLogout={logout} navigate={navigate} />;
  }
  return <Landing user={state.user} navigate={navigate} />;
}
