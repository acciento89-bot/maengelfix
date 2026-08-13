import { useEffect, useMemo, useState } from 'react';

const statusLabels = { draft:'Entwurf', sent:'Versendet', reply:'Rückmeldung', received:'Eingegangen', reviewing:'In Prüfung', commissioned:'Auftrag erstellt', scheduled:'Termin geplant', in_progress:'In Ausführung', resolved:'Erledigt' };
const managementStatusLabels = { received:'Eingegangen', reviewing:'In Prüfung', commissioned:'Auftrag erstellt', scheduled:'Termin geplant', in_progress:'In Ausführung', resolved:'Erledigt' };
const privateStatusLabels = { draft:'Entwurf', sent:'Versendet', reply:'Rückmeldung', in_progress:'In Bearbeitung', resolved:'Erledigt' };

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
        <button type="button" onClick={() => { navigate('/'); requestAnimationFrame(() => document.getElementById('ablauf')?.scrollIntoView({ behavior: 'smooth' })); }}>So funktioniert's</button>
        <button type="button" onClick={() => { navigate('/'); requestAnimationFrame(() => document.getElementById('funktionen')?.scrollIntoView({ behavior: 'smooth' })); }}>Funktionen</button>
        <button type="button" onClick={() => { navigate('/'); requestAnimationFrame(() => document.getElementById('tarife')?.scrollIntoView({ behavior: 'smooth' })); }}>Tarife</button>
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
              <button type="button" className="landingSecondary" onClick={() => document.getElementById('ablauf')?.scrollIntoView({ behavior: 'smooth' })}>So funktioniert's</button>
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


        <section className="pricingSection" id="tarife">
          <div className="sectionIntro"><span>TARIFE</span><h2>Für den einzelnen Mieter. Und für ganze Verwaltungen.</h2><p>MängelFix bekommt zwei klar getrennte Produktlinien. Die konkreten Preise legen wir vor dem Zahlungsstart fest.</p></div>
          <div className="pricingGrid">
            <article className="pricingCard privatePlan"><div className="planTag">PRIVAT</div><h3>MängelFix Privat</h3><p className="planLead">Für Mieter und private Nutzer, die ihre eigenen Vorgänge sauber dokumentieren möchten.</p><div className="planPrice"><strong>Einzeltarif</strong><span>1 persönliches Konto</span></div><ul><li>Eigene Mängel & Objekte</li><li>Fotos, Fristen und Verlauf</li><li>Professionelle PDF-Dokumentation</li><li>Persönliches Absenderprofil</li></ul><button onClick={() => navigate(user ? '/app' : '/registrieren')}>{user ? 'Zur App' : 'Privat starten'} →</button></article>
            <article className="pricingCard businessPlan"><div className="planTag">HAUSVERWALTUNG</div><h3>MängelFix Verwaltung</h3><p className="planLead">Für Hausverwaltungen, Vermieterbüros und Teams, die gemeinsam an Objekten und Vorgängen arbeiten.</p><div className="planPrice"><strong>Teamtarif</strong><span>Mehrere Mitarbeiterkonten</span></div><ul><li>Gemeinsamer Arbeitsbereich</li><li>Inhaber-, Admin- und Mitarbeiterrollen</li><li>Mitarbeiter selbst anlegen</li><li>Gemeinsamer Zugriff auf Mängel & Dokumente</li><li>Für viele Objekte skalierbar</li></ul><button onClick={() => navigate(user ? '/app' : '/registrieren')}>{user ? 'Team einrichten' : 'Verwaltung starten'} →</button></article>
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
      const pendingInvite = window.localStorage.getItem('maengelfix_pending_invite');
      navigate(pendingInvite ? `/einladung/${pendingInvite}` : '/app');
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
          {!register && <div className="authForgot"><button onClick={() => navigate('/passwort-vergessen')}>Passwort vergessen?</button></div>}
          <div className="authSwitch">{register ? 'Du hast bereits ein Konto?' : 'Noch kein MängelFix-Konto?'} <button onClick={() => navigate(register ? '/anmelden' : '/registrieren')}>{register ? 'Anmelden' : 'Kostenlos registrieren'}</button></div>
          <p className="legalHint">Mit der Nutzung gelten unsere <button onClick={() => navigate('/nutzungsbedingungen')}>Nutzungsbedingungen</button> und <button onClick={() => navigate('/datenschutz')}>Datenschutzhinweise</button>.</p>
        </section>
      </main>
      <PublicFooter navigate={navigate} />
    </div>
  );
}


function SimpleAccountPage({ mode, token, navigate }) {
  const [email,setEmail]=useState(''); const [password,setPassword]=useState(''); const [message,setMessage]=useState(''); const [error,setError]=useState(''); const [busy,setBusy]=useState(false);
  useEffect(()=>{ if(mode==='verify'&&token){ setBusy(true); api(`/api/auth/verify-email/${token}`).then(()=>setMessage('Deine E-Mail-Adresse wurde bestätigt.')).catch(e=>setError(e.message)).finally(()=>setBusy(false)); } },[mode,token]);
  async function submit(e){e.preventDefault();setBusy(true);setError('');setMessage('');try{if(mode==='forgot'){const d=await api('/api/auth/forgot-password',{method:'POST',body:JSON.stringify({email})});setMessage(d.message);}else if(mode==='reset'){await api(`/api/auth/reset-password/${token}`,{method:'POST',body:JSON.stringify({password})});setMessage('Dein Passwort wurde geändert. Du kannst dich jetzt anmelden.');}}catch(x){setError(x.message)}finally{setBusy(false)}}
  const title=mode==='forgot'?'Passwort vergessen':mode==='reset'?'Neues Passwort':'E-Mail bestätigen';
  return <div className="authStandalone"><PublicHeader navigate={navigate}/><main className="authStage accountActionStage"><section className="authPitch"><div className="landingEyebrow"><span/> MÄNGELFIX KONTO</div><h1>{title}</h1><p>{mode==='forgot'?'Wir senden dir einen sicheren Link zum Zurücksetzen.':mode==='reset'?'Lege ein neues Passwort mit mindestens 8 Zeichen fest.':'Wir prüfen deinen Bestätigungslink.'}</p></section><section className="authBox"><div className="authBoxHead"><span>KONTO</span><h2>{title}</h2></div>{mode!=='verify'&&<form onSubmit={submit} className="formStack">{mode==='forgot'?<label>E-Mail<input required type="email" value={email} onChange={e=>setEmail(e.target.value)}/></label>:<label>Neues Passwort<input required minLength="8" type="password" value={password} onChange={e=>setPassword(e.target.value)}/></label>}<button className="primaryButton authSubmit" disabled={busy}>{busy?'Einen Moment…':mode==='forgot'?'Link anfordern':'Passwort speichern'}</button></form>}{busy&&mode==='verify'&&<p>Bestätigung wird geprüft…</p>}{error&&<div className="errorBox">{error}</div>}{message&&<div className="successBox">{message}</div>}<div className="authSwitch"><button onClick={()=>navigate('/anmelden')}>Zur Anmeldung</button></div></section></main><PublicFooter navigate={navigate}/></div>;
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
  const [tenantLinks,setTenantLinks]=useState([]);
  useEffect(()=>{ api('/api/tenant-links').then(d=>setTenantLinks(d.links||[])).catch(()=>setTenantLinks([])); },[]);
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({ title: '', category: categories[0], description: '', propertyLabel: '', locationLabel: '', discoveredOn: today, recipientName: '', recipientEmail: '', recipientAddress: '', deadlineOn: '', destinationLinkId: '' });
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
          {tenantLinks.length>0&&<div className="digitalDelivery"><div><span>DIGITALE ÜBERMITTLUNG</span><h3>Mit Hausverwaltung verknüpft</h3><p>Du entscheidest für jeden Mangel neu, ob er privat bleibt oder direkt an eine verknüpfte Verwaltung geht.</p></div><label>Übermittlung<select value={form.destinationLinkId} onChange={e=>field('destinationLinkId',e.target.value)}><option value="">Nur privat dokumentieren</option>{tenantLinks.filter(l=>l.allow_tenant_submissions).map(l=><option key={l.id} value={l.id}>An {l.organization_name} · {l.property_name} · {l.unit_label}</option>)}</select></label></div>}
          <div className="subSection"><h3>{form.destinationLinkId?'Zusätzlicher Empfänger (optional)':'Empfänger'}</h3><p className="muted">Optional – Hausverwaltung, Vermieter oder anderer Ansprechpartner.</p></div>
          <div className="formGrid two"><label>Name / Firma<input value={form.recipientName} onChange={e => field('recipientName', e.target.value)} /></label><label>E-Mail<input type="email" value={form.recipientEmail} onChange={e => field('recipientEmail', e.target.value)} /></label></div>
          <label>Anschrift<textarea rows="2" placeholder="Straße, Hausnummer, PLZ Ort" value={form.recipientAddress} onChange={e => field('recipientAddress', e.target.value)} /></label>
          {error && <div className="errorBox">{error}</div>}
          <div className="modalActions"><button type="button" className="secondaryButton" onClick={onClose}>Abbrechen</button><button className="primaryButton" disabled={busy}>{busy ? 'Speichern…' : 'Vorgang anlegen'}</button></div>
        </form>
      </div>
    </div>
  );
}


function AssignmentPanel({ caseId, item, onChanged }) {
  const [options,setOptions]=useState(null); const [busy,setBusy]=useState(false); const [error,setError]=useState('');
  const [form,setForm]=useState({propertyId:item.property_id||'',unitId:item.unit_id||'',assignedUserId:item.assigned_user_id||''});
  useEffect(()=>{ api('/api/management/options').then(setOptions).catch(()=>setOptions({organization:null,properties:[],members:[]})); },[caseId]);
  if (!options || !options.organization) return null;
  const property=options.properties.find(p=>p.id===form.propertyId); const units=property?.units||[];
  async function save(){ setBusy(true);setError('');try{await api(`/api/cases/${caseId}/assignment`,{method:'PATCH',body:JSON.stringify(form)});await onChanged();}catch(e){setError(e.message);}finally{setBusy(false);} }
  return <section className="contentCard assignmentPanel"><div className="sectionTitle"><div><div className="cardKicker">VERWALTUNG</div><h3>Objekt & Zuständigkeit</h3><p className="muted">Ordne den Vorgang eindeutig einer Einheit und einem Mitarbeiter zu.</p></div></div><div className="formGrid three"><label>Objekt<select value={form.propertyId} onChange={e=>setForm({...form,propertyId:e.target.value,unitId:''})}><option value="">Nicht zugeordnet</option>{options.properties.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label><label>Einheit<select disabled={!form.propertyId} value={form.unitId} onChange={e=>setForm({...form,unitId:e.target.value})}><option value="">Keine Einheit</option>{units.map(u=><option key={u.id} value={u.id}>{u.label}</option>)}</select></label><label>Zuständig<select value={form.assignedUserId} onChange={e=>setForm({...form,assignedUserId:e.target.value})}><option value="">Nicht zugewiesen</option>{options.members.map(m=><option key={m.id} value={m.id}>{m.name}</option>)}</select></label></div>{error&&<div className="errorBox">{error}</div>}<button className="secondaryButton" disabled={busy} onClick={save}>{busy?'Speichern…':'Zuordnung speichern'}</button></section>;
}

function CaseDetail({ caseId, onBack, onUpdated, user, onProfile }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const [sharedMessage,setSharedMessage]=useState('');
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

  async function sendSharedMessage(event) {
    event.preventDefault(); if (!sharedMessage.trim()) return;
    setBusy(true); setError('');
    try { await api(`/api/cases/${caseId}/messages`, { method:'POST', body:JSON.stringify({message:sharedMessage}) }); setSharedMessage(''); await load(); onUpdated(); }
    catch(err){setError(err.message);} finally{setBusy(false);}
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
        <div className="detailActions">{!profileComplete && <button className="profileWarning" onClick={onProfile}>Absender ergänzen</button>}<a className="primaryButton linkButton" href={`/api/cases/${item.id}/pdf`} target="_blank" rel="noreferrer">PDF öffnen</a><a className="secondaryButton linkButton" href={`/api/cases/${item.id}/pdf?download=1`}>PDF herunterladen</a></div>
      </div>
      {!profileComplete && <div className="noticeBar"><b>Absenderprofil unvollständig.</b> Ergänze Straße, PLZ und Ort, damit deine Mängelanzeige einen vollständigen Absender enthält. <button onClick={onProfile}>Jetzt ergänzen</button></div>}
      {error && <div className="errorBox">{error}</div>}
      <div className="detailGrid">
        <section className="contentCard"><div className="cardKicker">FALLINHALT</div><h3>Beschreibung</h3><p className="descriptionText">{item.description}</p><div className="factsGrid"><div><span>Objekt</span><b>{item.property_label || '—'}</b></div><div><span>Raum / Ort</span><b>{item.location_label || '—'}</b></div><div><span>Rückmeldung bis</span><b>{fmtDate(item.deadline_on)}</b></div><div><span>Empfänger</span><b>{item.recipient_name || 'Noch nicht hinterlegt'}</b></div></div></section>
        <aside className="contentCard actionCard"><div className="cardKicker">VORGANG</div><h3>Status</h3><select disabled={busy} value={item.status} onChange={e => changeStatus(e.target.value)}>{Object.entries(data.viewerRole==='management'?managementStatusLabels:privateStatusLabels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select><p className="muted small">Statusänderungen werden automatisch im Verlauf protokolliert.</p><div className="sideInfo"><span>Fotobelege<b>{data.attachments.length}</b></span><span>Frist<b>{fmtDate(item.deadline_on)}</b></span></div></aside>
      </div>
      <AssignmentPanel caseId={caseId} item={item} onChanged={async()=>{await load();onUpdated();}} />
      {data.viewerRole==='management'&&<WorkOrderPanel caseId={caseId}/>}
      {item.submitted_by_tenant&&<section className="contentCard communicationCard"><div className="sectionTitle"><div><div className="cardKicker">KOMMUNIKATION</div><h3>{data.viewerRole==='management'?'Nachrichten an den Mieter':'Nachrichten mit der Hausverwaltung'}</h3><p className="muted">Diese Nachrichten sind für beide Seiten sichtbar und werden getrennt von internen Notizen gespeichert.</p></div></div><div className="messageThread">{(data.messages||[]).length?(data.messages||[]).map(msg=><div key={msg.id} className={`sharedMessage ${msg.user_id===user.id?'own':''}`}><div><b>{msg.actor_name}</b><span>{new Date(msg.created_at).toLocaleString('de-DE')}</span></div><p>{msg.message}</p></div>):<div className="emptyMini">Noch keine gemeinsamen Nachrichten.</div>}</div><form className="messageComposer" onSubmit={sendSharedMessage}><textarea rows="3" placeholder={data.viewerRole==='management'?'Nachricht an den Mieter…':'Nachricht an die Hausverwaltung…'} value={sharedMessage} onChange={e=>setSharedMessage(e.target.value)}/><button className="primaryButton" disabled={busy}>Nachricht senden</button></form></section>}
      <section className="contentCard"><div className="sectionTitle"><div><div className="cardKicker">BEWEISSICHERUNG</div><h3>Fotos & Belege</h3><p className="muted">Bis zu 5 Bilder pro Upload, jeweils maximal 10 MB.</p></div><label className="secondaryButton uploadButton">Bilder hinzufügen<input type="file" accept="image/*" multiple onChange={uploadImages} /></label></div>{data.attachments.length ? <div className="photoGrid">{data.attachments.map(file => <a key={file.id} href={`/api/attachments/${file.id}`} target="_blank" rel="noreferrer"><img src={`/api/attachments/${file.id}`} alt={file.original_name} /><span>{file.original_name}</span></a>)}</div> : <div className="emptyInline">Noch keine Bilder hinterlegt.</div>}</section>
      <section className="contentCard"><div className="sectionTitle"><div><div className="cardKicker">CHRONOLOGIE</div><h3>Verlauf</h3><p className="muted">{data.viewerRole==='management'&&item.submitted_by_tenant?'Interne Notizen sind nur für das Verwaltungsteam sichtbar. Statusänderungen bleiben für den Mieter nachvollziehbar.':'Notizen und Statusänderungen bleiben nachvollziehbar.'}</p></div></div><form className="noteForm" onSubmit={addNote}><input placeholder={data.viewerRole==='management'&&item.submitted_by_tenant?'Interne Notiz – für den Mieter nicht sichtbar…':'Neue Notiz, z. B. Hausverwaltung telefonisch erreicht…'} value={note} onChange={e => setNote(e.target.value)} /><button className="primaryButton" disabled={busy}>Notiz speichern</button></form><div className="timeline">{data.events.map(event => <div className="timelineItem" key={event.id}><div className="timelineDot"/><div><b>{event.event_type === 'created' ? 'Fall erstellt' : event.event_type === 'status' ? 'Status geändert' : 'Notiz'}</b><p>{event.note}</p><span>{new Date(event.created_at).toLocaleString('de-DE')}</span></div></div>)}</div></section>
    </div>
  );
}

function CaseRows({ cases, onSelect, emptyText = 'Keine Vorgänge vorhanden.' }) {
  if (!cases.length) return <div className="emptyCard workspaceEmpty">{emptyText}</div>;
  return <div className="workspaceTable">{cases.map(item => <button key={item.id} className="tableRow" onClick={() => onSelect(item.id)}><div className="rowAlert">!</div><div className="rowMain"><div><h3>{item.title}</h3><span className={`status status-${item.status}`}>{statusLabels[item.status]}</span></div><p>{item.property_label || item.location_label || item.category}</p></div><div className="rowMeta"><span>{item.category}</span><span>{item.attachment_count} Bild{item.attachment_count === 1 ? '' : 'er'}</span></div><div className="rowDeadline">{item.deadline_on ? <><small>Frist</small><b>{fmtDate(item.deadline_on)}</b></> : <span>Keine Frist</span>}</div><span className="rowArrow">→</span></button>)}</div>;
}


function ManagementOverview({ user, cases, onNew, onSelect, setView, management }) {
  const m=management.metrics||{}; const recent=management.recent||[]; const members=management.members||[];
  return <div className="workspacePage managementHome"><div className="workspaceHeading"><div><span>VERWALTUNG</span><h1>{management.organization.name}</h1><p>Guten Morgen, {user.name.split(' ')[0]}. Hier siehst du Objekte, offene Vorgänge und Team-Auslastung auf einen Blick.</p></div><button className="workspacePrimary" onClick={onNew}>+ Mangel erfassen</button></div><div className="managementMetrics"><button onClick={()=>setView('objects')}><span>OBJEKTE</span><strong>{m.properties||0}</strong><small>{m.units||0} Einheiten</small></button><button onClick={()=>setView('cases')}><span>OFFENE MÄNGEL</span><strong>{m.open||0}</strong><small>{m.unassigned||0} ohne Zuständigkeit</small></button><button onClick={()=>setView('deadlines')} className={m.overdue?'attention':''}><span>ÜBERFÄLLIG</span><strong>{m.overdue||0}</strong><small>Fristen überschritten</small></button><button onClick={()=>setView('objects')}><span>KONTAKTE / MIETER</span><strong>{m.contacts||0}</strong><small>in der Verwaltung</small></button></div><div className="dashboardColumns managementColumns"><section className="workspacePanel"><div className="panelHead"><div><span>AKTUELLE VORGÄNGE</span><h2>Zuletzt bearbeitet</h2></div><button onClick={()=>setView('cases')}>Alle anzeigen →</button></div><CaseRows cases={recent.map(x=>({...x,attachment_count:0,property_label:x.property_name||x.unit_label||''}))} onSelect={onSelect} /></section><aside className="workspacePanel workloadPanel"><div className="panelHead"><div><span>TEAM</span><h2>Offene Zuständigkeiten</h2></div><button onClick={()=>setView('team')}>Team →</button></div>{members.map(member=><div className="workloadRow" key={member.id}><div>{member.name.slice(0,1).toUpperCase()}</div><span><b>{member.name}</b><small>{member.role==='owner'?'Inhaber':member.role==='admin'?'Admin':'Mitarbeiter'}</small></span><strong>{member.open_cases}</strong></div>)}</aside></div></div>;
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



function ManagedObjectsView({ onSelect }) {
  const [properties,setProperties]=useState([]); const [propertyId,setPropertyId]=useState(null); const [detail,setDetail]=useState(null); const [unitDetail,setUnitDetail]=useState(null);
  const [showNew,setShowNew]=useState(false); const [showUnit,setShowUnit]=useState(false); const [showContact,setShowContact]=useState(false); const [contacts,setContacts]=useState([]); const [error,setError]=useState('');
  const [form,setForm]=useState({name:'',street:'',postalCode:'',city:'',notes:''}); const [unitForm,setUnitForm]=useState({label:'',floor:'',positionLabel:'',areaSqm:''}); const [contactForm,setContactForm]=useState({name:'',email:'',phone:'',street:'',postalCode:'',city:'',notes:'',contactType:'tenant'});
  async function loadProperties(){try{setProperties((await api('/api/properties')).properties)}catch(e){setError(e.message)}}
  async function loadProperty(id){try{setDetail(await api(`/api/properties/${id}`));setPropertyId(id);setUnitDetail(null)}catch(e){setError(e.message)}}
  async function loadUnit(id){try{setUnitDetail(await api(`/api/units/${id}`));setContacts((await api('/api/contacts')).contacts)}catch(e){setError(e.message)}}
  useEffect(()=>{loadProperties()},[]);
  async function createProperty(e){e.preventDefault();try{const d=await api('/api/properties',{method:'POST',body:JSON.stringify(form)});setShowNew(false);setForm({name:'',street:'',postalCode:'',city:'',notes:''});await loadProperties();await loadProperty(d.property.id)}catch(x){setError(x.message)}}
  async function createUnit(e){e.preventDefault();try{const d=await api(`/api/properties/${propertyId}/units`,{method:'POST',body:JSON.stringify(unitForm)});setShowUnit(false);setUnitForm({label:'',floor:'',positionLabel:'',areaSqm:''});await loadProperty(propertyId);await loadUnit(d.unit.id)}catch(x){setError(x.message)}}
  async function createContact(e){e.preventDefault();try{const d=await api('/api/contacts',{method:'POST',body:JSON.stringify(contactForm)});await api(`/api/units/${unitDetail.unit.id}/contacts`,{method:'POST',body:JSON.stringify({contactId:d.contact.id,role:'tenant',isPrimary:unitDetail.contacts.length===0})});setShowContact(false);setContactForm({name:'',email:'',phone:'',street:'',postalCode:'',city:'',notes:'',contactType:'tenant'});await loadUnit(unitDetail.unit.id);await loadProperty(propertyId)}catch(x){setError(x.message)}}
  async function attachContact(contactId){try{await api(`/api/units/${unitDetail.unit.id}/contacts`,{method:'POST',body:JSON.stringify({contactId,role:'tenant',isPrimary:unitDetail.contacts.length===0})});await loadUnit(unitDetail.unit.id);await loadProperty(propertyId)}catch(x){setError(x.message)}}
  async function detachContact(contactId){try{await api(`/api/units/${unitDetail.unit.id}/contacts/${contactId}`,{method:'DELETE'});await loadUnit(unitDetail.unit.id);await loadProperty(propertyId)}catch(x){setError(x.message)}}
  async function inviteTenant(contact){try{const d=await api(`/api/contacts/${contact.id}/invitations`,{method:'POST',body:JSON.stringify({unitId:unitDetail.unit.id})}); if(d.invitation.delivery==='email') alert(`Einladung wurde an ${d.invitation.email} gesendet.`); else { await navigator.clipboard?.writeText(d.invitation.inviteUrl); prompt('SMTP ist noch nicht eingerichtet. Einladung-Link wurde erzeugt – bitte kopieren und dem Mieter senden:',d.invitation.inviteUrl); } await loadUnit(unitDetail.unit.id);}catch(x){setError(x.message)}}

  if(unitDetail) { const u=unitDetail.unit; const available=contacts.filter(c=>!unitDetail.contacts.some(x=>x.id===c.id)); return <div className="workspacePage unitDetailPage"><button className="backButton" onClick={()=>setUnitDetail(null)}>← {u.property_name}</button><div className="workspaceHeading"><div><span>EINHEIT</span><h1>{u.label}</h1><p>{[u.floor,u.position_label,u.area_sqm?`${u.area_sqm} m²`:null].filter(Boolean).join(' · ')}</p></div><button className="workspacePrimary" onClick={()=>setShowContact(true)}>+ Mieter / Kontakt</button></div>{error&&<div className="errorBox">{error}</div>}<div className="unitDetailGrid"><section className="workspacePanel"><div className="panelHead"><div><span>MIETER & KONTAKTE</span><h2>{unitDetail.contacts.length} zugeordnet</h2></div></div>{unitDetail.contacts.length?unitDetail.contacts.map(c=><article className="tenantCard" key={c.id}><div className="tenantAvatar">{c.name.slice(0,1).toUpperCase()}</div><div><h3>{c.name}{c.is_primary&&<span>HAUPTKONTAKT</span>}</h3><p>{c.email||'Keine E-Mail'}{c.phone?` · ${c.phone}`:''}</p><small>{[c.street,[c.postal_code,c.city].filter(Boolean).join(' ')].filter(Boolean).join(', ')||'Keine Anschrift hinterlegt'}</small></div><div className="tenantActions">{c.digitally_linked?<span className="linkedBadge">DIGITAL VERKNÜPFT</span>:<button className="inviteTenantButton" disabled={!c.email} onClick={()=>inviteTenant(c)}>{c.email?'Zu MängelFix einladen':'E-Mail fehlt'}</button>}<button onClick={()=>detachContact(c.id)}>Entfernen</button></div></article>):<div className="emptyMini">Noch kein Mieter oder Kontakt zugeordnet.</div>}{available.length>0&&<div className="existingContact"><label>Vorhandenen Kontakt zuordnen<select defaultValue="" onChange={e=>{if(e.target.value)attachContact(e.target.value);e.target.value='';}}><option value="">Kontakt auswählen…</option>{available.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label></div>}</section><aside className="workspacePanel unitFacts"><div className="panelHead"><div><span>STAMMDATEN</span><h2>Einheit</h2></div></div><dl><dt>Objekt</dt><dd>{u.property_name}</dd><dt>Etage</dt><dd>{u.floor||'—'}</dd><dt>Lage</dt><dd>{u.position_label||'—'}</dd><dt>Fläche</dt><dd>{u.area_sqm?`${u.area_sqm} m²`:'—'}</dd></dl></aside></div><section className="workspacePanel"><div className="panelHead"><div><span>MÄNGEL</span><h2>Vorgänge dieser Einheit</h2></div></div><CaseRows cases={unitDetail.cases.map(x=>({...x,attachment_count:x.attachment_count||0}))} onSelect={onSelect} emptyText="Noch kein Mangel für diese Einheit." /></section>{showContact&&<div className="modalBackdrop" onMouseDown={()=>setShowContact(false)}><div className="modal proModal" onMouseDown={e=>e.stopPropagation()}><div className="modalHeader"><div><div className="eyebrow">NEUER KONTAKT</div><h2>Mieter / Kontakt anlegen</h2></div><button className="iconButton" onClick={()=>setShowContact(false)}>×</button></div><form className="caseForm" onSubmit={createContact}><label>Name<input required value={contactForm.name} onChange={e=>setContactForm({...contactForm,name:e.target.value})}/></label><div className="formGrid two"><label>E-Mail<input type="email" value={contactForm.email} onChange={e=>setContactForm({...contactForm,email:e.target.value})}/></label><label>Telefon<input value={contactForm.phone} onChange={e=>setContactForm({...contactForm,phone:e.target.value})}/></label><label>Straße<input value={contactForm.street} onChange={e=>setContactForm({...contactForm,street:e.target.value})}/></label><label>PLZ<input value={contactForm.postalCode} onChange={e=>setContactForm({...contactForm,postalCode:e.target.value})}/></label><label>Ort<input value={contactForm.city} onChange={e=>setContactForm({...contactForm,city:e.target.value})}/></label></div><label>Interne Notiz<textarea rows="3" value={contactForm.notes} onChange={e=>setContactForm({...contactForm,notes:e.target.value})}/></label><div className="modalActions"><button type="button" className="secondaryButton" onClick={()=>setShowContact(false)}>Abbrechen</button><button className="primaryButton">Kontakt anlegen & zuordnen</button></div></form></div></div>}</div> }

  if(propertyId&&detail) return <div className="workspacePage propertyDetailPage"><button className="backButton" onClick={()=>{setPropertyId(null);setDetail(null)}}>← Alle Objekte</button><div className="workspaceHeading"><div><span>OBJEKT</span><h1>{detail.property.name}</h1><p>{[detail.property.street,[detail.property.postal_code,detail.property.city].filter(Boolean).join(' ')].filter(Boolean).join(' · ')}</p></div><div className="propertyHeaderActions"><label className="tenantSubmissionToggle"><input type="checkbox" checked={detail.property.allow_tenant_submissions!==false} onChange={async e=>{try{await api(`/api/properties/${propertyId}/tenant-submissions`,{method:'PATCH',body:JSON.stringify({enabled:e.target.checked})});await loadProperty(propertyId)}catch(x){setError(x.message)}}}/><span>Digitale Mietermeldungen</span></label><button className="workspacePrimary" onClick={()=>setShowUnit(true)}>+ Einheit anlegen</button></div></div><div className="metricGrid"><div><span>EINHEITEN</span><strong>{detail.units.length}</strong><small>Wohnungen / Gewerbe</small></div><div><span>VORGÄNGE</span><strong>{detail.cases.length}</strong><small>am Objekt</small></div><div><span>OFFEN</span><strong>{detail.cases.filter(x=>x.status!=='resolved').length}</strong><small>noch nicht erledigt</small></div><div><span>KONTAKTE</span><strong>{detail.units.reduce((n,u)=>n+Number(u.contact_count||0),0)}</strong><small>Einheiten-Zuordnungen</small></div></div><section className="workspacePanel"><div className="panelHead"><div><span>EINHEITEN</span><h2>Wohnungen & Bereiche</h2></div></div><div className="unitGrid proUnits">{detail.units.length?detail.units.map(u=><button className="unitCard" key={u.id} onClick={()=>loadUnit(u.id)}><span>EINHEIT</span><h3>{u.label}</h3><p>{[u.floor,u.position_label].filter(Boolean).join(' · ')||'Keine Zusatzangaben'}</p><div><b>{u.open_case_count}</b> offen · <b>{u.contact_count}</b> Kontakte</div><strong>→</strong></button>):<div className="emptyCard workspaceEmpty">Noch keine Einheiten angelegt.</div>}</div></section><section className="workspacePanel"><div className="panelHead"><div><span>VORGÄNGE</span><h2>Mängel am Objekt</h2></div></div><CaseRows cases={detail.cases} onSelect={onSelect} /></section>{showUnit&&<div className="modalBackdrop" onMouseDown={()=>setShowUnit(false)}><div className="modal proModal" onMouseDown={e=>e.stopPropagation()}><div className="modalHeader"><div><div className="eyebrow">NEUE EINHEIT</div><h2>Wohnung / Einheit anlegen</h2></div><button className="iconButton" onClick={()=>setShowUnit(false)}>×</button></div><form className="caseForm" onSubmit={createUnit}><label>Bezeichnung<input required placeholder="z. B. EG links / WE 01" value={unitForm.label} onChange={e=>setUnitForm({...unitForm,label:e.target.value})}/></label><div className="formGrid two"><label>Etage<input value={unitForm.floor} onChange={e=>setUnitForm({...unitForm,floor:e.target.value})}/></label><label>Lage<input value={unitForm.positionLabel} onChange={e=>setUnitForm({...unitForm,positionLabel:e.target.value})}/></label><label>Fläche m²<input type="number" step="0.1" value={unitForm.areaSqm} onChange={e=>setUnitForm({...unitForm,areaSqm:e.target.value})}/></label></div><div className="modalActions"><button type="button" className="secondaryButton" onClick={()=>setShowUnit(false)}>Abbrechen</button><button className="primaryButton">Einheit speichern</button></div></form></div></div>}</div>;

  return <div className="workspacePage"><div className="workspaceHeading"><div><span>OBJEKTE</span><h1>Gebäude & Liegenschaften</h1><p>Objekte, Einheiten, Mieter und Vorgänge zentral verwalten.</p></div><button className="workspacePrimary" onClick={()=>setShowNew(true)}>+ Objekt anlegen</button></div>{error&&<div className="errorBox">{error}</div>}<div className="managedObjectGrid">{properties.length?properties.map(p=><button className="managedObjectCard" key={p.id} onClick={()=>loadProperty(p.id)}><div className="managedObjectIcon">⌂</div><div><span>OBJEKT</span><h2>{p.name}</h2><p>{[p.street,[p.postal_code,p.city].filter(Boolean).join(' ')].filter(Boolean).join(' · ')||'Keine Adresse hinterlegt'}</p></div><div className="managedObjectStats"><span><b>{p.unit_count}</b> Einheiten</span><span><b>{p.open_case_count}</b> offen</span></div><strong>→</strong></button>):<div className="emptyCard workspaceEmpty">Noch kein Objekt angelegt.</div>}</div>{showNew&&<div className="modalBackdrop" onMouseDown={()=>setShowNew(false)}><div className="modal proModal" onMouseDown={e=>e.stopPropagation()}><div className="modalHeader"><div><div className="eyebrow">NEUES OBJEKT</div><h2>Gebäude anlegen</h2></div><button className="iconButton" onClick={()=>setShowNew(false)}>×</button></div><form className="caseForm" onSubmit={createProperty}><label>Objektname<input required value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></label><label>Straße & Hausnummer<input value={form.street} onChange={e=>setForm({...form,street:e.target.value})}/></label><div className="formGrid two"><label>PLZ<input value={form.postalCode} onChange={e=>setForm({...form,postalCode:e.target.value})}/></label><label>Ort<input value={form.city} onChange={e=>setForm({...form,city:e.target.value})}/></label></div><label>Interne Notiz<textarea rows="3" value={form.notes} onChange={e=>setForm({...form,notes:e.target.value})}/></label><div className="modalActions"><button type="button" className="secondaryButton" onClick={()=>setShowNew(false)}>Abbrechen</button><button className="primaryButton">Objekt speichern</button></div></form></div></div>}</div>;
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
  return <div className="workspacePage"><div className="workspaceHeading"><div><span>PROFIL</span><h1>Absender & Konto</h1><p>Diese Angaben erscheinen als Absender in deiner MängelFix-PDF.</p></div></div><div className="profileLayout"><form className="workspacePanel profileForm" onSubmit={save}><div className="panelHead"><div><span>ABSENDERDATEN</span><h2>Deine Kontaktdaten</h2></div></div><div className="formGrid two"><label>Name<input required value={form.name} onChange={e => field('name', e.target.value)} /></label><label>E-Mail<input disabled value={user.email} /></label><label>Straße & Hausnummer<input required placeholder="Musterstraße 12" value={form.street} onChange={e => field('street', e.target.value)} /></label><label>Telefon <em>optional</em><input placeholder="+49 …" value={form.phone} onChange={e => field('phone', e.target.value)} /></label><label>PLZ<input required value={form.postalCode} onChange={e => field('postalCode', e.target.value)} /></label><label>Ort<input required value={form.city} onChange={e => field('city', e.target.value)} /></label></div><label>Land<input value={form.country} onChange={e => field('country', e.target.value)} /></label>{error && <div className="errorBox">{error}</div>}{message && <div className="successBox">{message}</div>}{!user.emailVerified&&<div className="verificationNotice"><div><b>E-Mail noch nicht bestätigt</b><span>Bestätige deine Adresse für Kontosicherheit und Benachrichtigungen.</span></div><button type="button" className="secondaryButton" onClick={async()=>{try{const d=await api('/api/auth/resend-verification',{method:'POST'});setMessage(d.sent?'Bestätigungs-E-Mail wurde versendet.':'Mailversand ist noch nicht konfiguriert.');}catch(e){setError(e.message)}}}>Bestätigung senden</button></div>}<div className="profileActions"><button className="primaryButton" disabled={busy}>{busy ? 'Speichern…' : 'Profil speichern'}</button></div></form><aside className="senderPreview"><span>PDF-VORSCHAU</span><h3>Absender</h3><p><b>{form.name || 'Dein Name'}</b><br />{form.street || 'Straße & Hausnummer'}<br />{form.postalCode || 'PLZ'} {form.city || 'Ort'}<br />{form.country || 'Deutschland'}<br />{user.email}{form.phone ? <><br />{form.phone}</> : null}</p><small>Diese Angaben werden nicht öffentlich angezeigt. Sie werden für dein Konto und die von dir erzeugten Dokumente verwendet.</small></aside></div></div>;
}



function NotificationsView({ onSelect, refreshUnread }) {
  const [data,setData]=useState({notifications:[],unread:0}); const [error,setError]=useState('');
  async function load(){try{setData(await api('/api/notifications'));refreshUnread?.();}catch(e){setError(e.message)}}
  useEffect(()=>{load()},[]);
  async function open(item){try{if(!item.read_at)await api(`/api/notifications/${item.id}/read`,{method:'POST'});if(item.case_id)onSelect(item.case_id);else if(item.link)window.location.href=item.link;else await load();refreshUnread?.();}catch(e){setError(e.message)}}
  async function readAll(){try{await api('/api/notifications/read-all',{method:'POST'});await load();refreshUnread?.();}catch(e){setError(e.message)}}
  return <div className="workspacePage"><div className="workspaceHeading"><div><span>BENACHRICHTIGUNGEN</span><h1>Was deine Aufmerksamkeit braucht</h1><p>Mietermeldungen, Nachrichten, Statusänderungen und wichtige Vorgänge an einer Stelle.</p></div>{data.unread>0&&<button className="secondaryButton" onClick={readAll}>Alle als gelesen markieren</button>}</div>{error&&<div className="errorBox">{error}</div>}<div className="notificationList">{data.notifications.length?data.notifications.map(n=><button key={n.id} className={`notificationRow ${n.read_at?'':'unread'}`} onClick={()=>open(n)}><div className="notificationIcon">{n.type==='tenant_case'?'!':n.type==='message'?'✉':n.type==='status'?'↻':'•'}</div><div><span>{n.type.replace('_',' ').toUpperCase()}</span><h3>{n.title}</h3><p>{n.body||''}</p><small>{new Date(n.created_at).toLocaleString('de-DE')}</small></div>{!n.read_at&&<i/>}</button>):<div className="emptyCard workspaceEmpty">Keine Benachrichtigungen vorhanden.</div>}</div></div>;
}

function AuditView() {
  const [logs,setLogs]=useState([]); const [error,setError]=useState('');
  useEffect(()=>{api('/api/audit').then(d=>setLogs(d.logs||[])).catch(e=>setError(e.message))},[]);
  const labels={tenant_submitted:'Mietermeldung',status_changed:'Status',assignment_changed:'Zuordnung',note_added:'Interne Notiz',message_sent:'Nachricht',work_order_created:'Arbeitsauftrag'};
  return <div className="workspacePage"><div className="workspaceHeading"><div><span>AKTIVITÄTSPROTOKOLL</span><h1>Wer hat was gemacht?</h1><p>Nachvollziehbare Historie wichtiger Aktionen im Verwaltungs-Arbeitsbereich.</p></div></div>{error&&<div className="errorBox">{error}</div>}<div className="auditList">{logs.length?logs.map(log=><article key={log.id} className="auditRow"><div className="auditTime"><b>{new Date(log.created_at).toLocaleDateString('de-DE')}</b><span>{new Date(log.created_at).toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'})}</span></div><div><span>{labels[log.action]||log.action}</span><h3>{log.summary}</h3><p>{log.actor_name?`Durch ${log.actor_name}`:'Automatischer Vorgang'}</p></div></article>):<div className="emptyCard workspaceEmpty">Noch keine protokollierten Verwaltungsaktionen.</div>}</div></div>;
}

function TeamView() {
  const [team, setTeam] = useState({ organization: null, members: [] });
  const [orgName, setOrgName] = useState('');
  const [member, setMember] = useState({ name: '', email: '', password: '', role: 'member' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function load() {
    try { setTeam(await api('/api/team')); }
    catch (err) { setError(err.message); }
  }
  useEffect(() => { load(); }, []);

  async function createOrganization(event) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('');
    try { await api('/api/team', { method: 'POST', body: JSON.stringify({ name: orgName }) }); setMessage('Hausverwaltungs-Arbeitsbereich angelegt. Ab jetzt werden neue Vorgänge mit deinem Team geteilt.'); setOrgName(''); await load(); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function createMember(event) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('');
    try { await api('/api/team/members', { method: 'POST', body: JSON.stringify(member) }); setMessage('Mitarbeiterkonto erstellt. Die Person kann sich sofort mit der angegebenen E-Mail und dem Startpasswort anmelden.'); setMember({ name: '', email: '', password: '', role: 'member' }); await load(); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  if (!team.organization) {
    return <div className="workspacePage"><div className="workspaceHeading"><div><span>HAUSVERWALTUNG</span><h1>Gemeinsam statt mit geteilten Passwörtern.</h1><p>Privatkonten bleiben persönlich. Für Verwaltungen richtest du einen gemeinsamen Arbeitsbereich mit eigenen Mitarbeiter-Logins ein.</p></div></div><div className="teamIntroGrid"><section className="workspacePanel teamSetup"><div className="panelHead"><div><span>TEAMTARIF</span><h2>Hausverwaltung einrichten</h2></div></div><p>Nach dem Einrichten sehen alle Teammitglieder die gemeinsamen Vorgänge der Verwaltung. Du wirst automatisch Inhaber.</p><form onSubmit={createOrganization}><label>Name der Hausverwaltung<input required placeholder="z. B. Muster Hausverwaltung GmbH" value={orgName} onChange={e => setOrgName(e.target.value)} /></label>{error && <div className="errorBox">{error}</div>}{message && <div className="successBox">{message}</div>}<button className="primaryButton" disabled={busy}>{busy ? 'Einrichten…' : 'Arbeitsbereich einrichten'}</button></form></section><aside className="teamBenefits"><span>HAUSVERWALTUNG</span><h3>Was der Teamtarif vorbereitet</h3><ul><li>Eigene Logins für Mitarbeiter</li><li>Rollen: Inhaber, Admin, Mitarbeiter</li><li>Gemeinsame Mängel und Dokumente</li><li>Kein Teilen eines Master-Passworts</li><li>Basis für spätere Objekt- und Rechteverwaltung</li></ul></aside></div></div>;
  }

  const canManage = ['owner', 'admin'].includes(team.organization.role);
  return <div className="workspacePage"><div className="workspaceHeading"><div><span>TEAM</span><h1>{team.organization.name}</h1><p>Gemeinsamer Hausverwaltungs-Arbeitsbereich · Rolle: {team.organization.role === 'owner' ? 'Inhaber' : team.organization.role === 'admin' ? 'Admin' : 'Mitarbeiter'}</p></div><div className="teamPlanBadge">VERWALTUNG · TEAMTARIF</div></div>{error && <div className="errorBox">{error}</div>}{message && <div className="successBox">{message}</div>}<div className="teamColumns"><section className="workspacePanel"><div className="panelHead"><div><span>MITARBEITER</span><h2>{team.members.length} Teammitglied{team.members.length === 1 ? '' : 'er'}</h2></div></div><div className="memberList">{team.members.map(item => <div className="memberRow" key={item.id}><div>{item.name.slice(0,1).toUpperCase()}</div><p><b>{item.name}</b><span>{item.email}</span></p><strong>{item.role === 'owner' ? 'INHABER' : item.role === 'admin' ? 'ADMIN' : 'MITARBEITER'}</strong></div>)}</div></section>{canManage && <form className="workspacePanel addMemberForm" onSubmit={createMember}><div className="panelHead"><div><span>NEUER ZUGANG</span><h2>Mitarbeiter anlegen</h2></div></div><label>Name<input required value={member.name} onChange={e => setMember({ ...member, name: e.target.value })} /></label><label>E-Mail<input required type="email" value={member.email} onChange={e => setMember({ ...member, email: e.target.value })} /></label><label>Startpasswort<input required minLength="8" type="password" value={member.password} onChange={e => setMember({ ...member, password: e.target.value })} placeholder="Mindestens 8 Zeichen" /></label><label>Rolle<select value={member.role} onChange={e => setMember({ ...member, role: e.target.value })}><option value="member">Mitarbeiter</option><option value="admin">Admin</option></select></label><small>Das Startpasswort wird nicht angezeigt oder per E-Mail versendet. Teile es der Person über einen sicheren Weg mit.</small><button className="primaryButton" disabled={busy}>{busy ? 'Anlegen…' : 'Mitarbeiterkonto anlegen'}</button></form>}</div></div>;
}


function InvitationPage({ token, user, navigate }) {
  const [data,setData]=useState(null); const [error,setError]=useState(''); const [busy,setBusy]=useState(false); const [done,setDone]=useState(false);
  useEffect(()=>{window.localStorage.setItem('maengelfix_pending_invite',token);api(`/api/invitations/${token}`).then(setData).catch(e=>setError(e.message));},[token]);
  async function accept(){setBusy(true);setError('');try{await api(`/api/invitations/${token}/accept`,{method:'POST'});window.localStorage.removeItem('maengelfix_pending_invite');setDone(true);}catch(e){setError(e.message)}finally{setBusy(false)}}
  if(done)return <div className="invitationPage"><PublicHeader user={user} navigate={navigate}/><main className="invitationCard successInvitation"><Logo/><span>VERKNÜPFUNG AKTIV</span><h1>Deine Wohnung ist verbunden.</h1><p>Bei jedem neuen Mangel kannst du nun selbst entscheiden, ob er privat bleibt oder direkt an die Hausverwaltung übermittelt wird.</p><button className="primaryButton" onClick={()=>navigate('/app')}>MängelFix öffnen →</button></main><PublicFooter navigate={navigate}/></div>;
  return <div className="invitationPage"><PublicHeader user={user} navigate={navigate}/><main className="invitationCard"><Logo/><span>MIETER-EINLADUNG</span>{error?<div className="errorBox">{error}</div>:!data?<p>Einladung wird geladen…</p>:<><h1>{data.invitation.organization_name} möchte sich mit dir verbinden.</h1><div className="invitationFacts"><div><small>Objekt</small><b>{data.invitation.property_name}</b><span>{[data.invitation.street,[data.invitation.postal_code,data.invitation.city].filter(Boolean).join(' ')].filter(Boolean).join(', ')}</span></div><div><small>Einheit</small><b>{data.invitation.unit_label}</b></div></div><div className="privacyPromise"><b>Deine privaten Vorgänge bleiben privat.</b><p>Die Hausverwaltung sieht nur Mängel, die du später ausdrücklich an sie übermittelst. Die Verknüpfung allein gibt keinen Zugriff auf deine übrigen Inhalte.</p></div>{user?<><p>Angemeldet als <b>{user.email}</b>.</p><button className="primaryButton" disabled={busy} onClick={accept}>{busy?'Verknüpfen…':'Verknüpfung akzeptieren'}</button></>:<div className="inviteAuth"><p>Bitte registriere dich mit <b>{data.invitation.email}</b> oder melde dich mit einem bestehenden Konto unter dieser E-Mail-Adresse an.</p><button className="primaryButton" onClick={()=>navigate('/registrieren')}>Privatkonto erstellen</button><button className="secondaryButton" onClick={()=>navigate('/anmelden')}>Anmelden</button></div>}</>}</main><PublicFooter navigate={navigate}/></div>;
}



const tradeOptions=['SHK / Heizung / Sanitär','Elektro','Maler / Trockenbau','Fenster / Türen','Dach / Fassade','Schlüsseldienst','Reinigung / Trocknung','Hausmeister','Garten / Außenanlagen','Sonstiges'];
const orderStatusLabels={draft:'Entwurf',sent:'Versendet',accepted:'Angenommen',scheduled:'Termin geplant',completed:'Erledigt',declined:'Abgelehnt'};

function ProvidersView(){
  const [providers,setProviders]=useState([]); const [show,setShow]=useState(false); const [error,setError]=useState(''); const [busy,setBusy]=useState(false);
  const [form,setForm]=useState({companyName:'',trade:tradeOptions[0],contactName:'',email:'',phone:'',street:'',postalCode:'',city:'',notes:''});
  async function load(){try{setProviders((await api('/api/providers')).providers)}catch(e){setError(e.message)}} useEffect(()=>{load()},[]);
  async function create(e){e.preventDefault();setBusy(true);setError('');try{await api('/api/providers',{method:'POST',body:JSON.stringify(form)});setShow(false);setForm({companyName:'',trade:tradeOptions[0],contactName:'',email:'',phone:'',street:'',postalCode:'',city:'',notes:''});await load()}catch(x){setError(x.message)}finally{setBusy(false)}}
  return <div className="workspacePage"><div className="workspaceHeading"><div><span>DIENSTLEISTER</span><h1>Handwerker & Partnerfirmen</h1><p>Firmenstammdaten nach Gewerk verwalten und direkt für Arbeitsaufträge verwenden.</p></div><button className="workspacePrimary" onClick={()=>setShow(true)}>+ Dienstleister anlegen</button></div>{error&&<div className="errorBox">{error}</div>}<div className="providerGrid">{providers.length?providers.map(p=><article className="providerCard" key={p.id}><div className="providerTrade">{p.trade}</div><h2>{p.company_name}</h2><p>{p.contact_name||'Kein Ansprechpartner'}{p.email?` · ${p.email}`:''}</p><small>{[p.street,[p.postal_code,p.city].filter(Boolean).join(' ')].filter(Boolean).join(', ')||'Keine Anschrift'}</small><div className="providerStats"><span><b>{p.open_order_count}</b> offen</span><span><b>{p.order_count}</b> gesamt</span></div></article>):<div className="emptyCard workspaceEmpty">Noch keine Dienstleister angelegt.</div>}</div>{show&&<div className="modalBackdrop" onMouseDown={()=>setShow(false)}><div className="modal proModal" onMouseDown={e=>e.stopPropagation()}><div className="modalHeader"><div><div className="eyebrow">NEUER DIENSTLEISTER</div><h2>Firma anlegen</h2></div><button className="iconButton" onClick={()=>setShow(false)}>×</button></div><form className="caseForm" onSubmit={create}><div className="formGrid two"><label>Firma<input required value={form.companyName} onChange={e=>setForm({...form,companyName:e.target.value})}/></label><label>Gewerk<select value={form.trade} onChange={e=>setForm({...form,trade:e.target.value})}>{tradeOptions.map(x=><option key={x}>{x}</option>)}</select></label><label>Ansprechpartner<input value={form.contactName} onChange={e=>setForm({...form,contactName:e.target.value})}/></label><label>E-Mail<input type="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></label><label>Telefon<input value={form.phone} onChange={e=>setForm({...form,phone:e.target.value})}/></label><label>Straße<input value={form.street} onChange={e=>setForm({...form,street:e.target.value})}/></label><label>PLZ<input value={form.postalCode} onChange={e=>setForm({...form,postalCode:e.target.value})}/></label><label>Ort<input value={form.city} onChange={e=>setForm({...form,city:e.target.value})}/></label></div><label>Interne Notiz<textarea rows="3" value={form.notes} onChange={e=>setForm({...form,notes:e.target.value})}/></label>{error&&<div className="errorBox">{error}</div>}<div className="modalActions"><button type="button" className="secondaryButton" onClick={()=>setShow(false)}>Abbrechen</button><button className="primaryButton" disabled={busy}>{busy?'Speichern…':'Dienstleister speichern'}</button></div></form></div></div>}</div>;
}

function WorkOrdersView({onSelectCase}){
  const [orders,setOrders]=useState([]); const [error,setError]=useState(''); useEffect(()=>{api('/api/work-orders').then(d=>setOrders(d.orders)).catch(e=>setError(e.message))},[]);
  return <div className="workspacePage"><div className="workspaceHeading"><div><span>ARBEITSAUFTRÄGE</span><h1>Beauftragte Dienstleister</h1><p>Versand, Annahme, Termine und Rückmeldungen aus einem Vorgang heraus nachvollziehen.</p></div></div>{error&&<div className="errorBox">{error}</div>}<div className="orderList">{orders.length?orders.map(o=><article className="orderRow" key={o.id}><div className="orderMark">A</div><div><span>{o.trade}</span><h3>{o.title}</h3><p>{o.company_name} · {o.property_name||o.property_label||'ohne Objekt'}{o.unit_label?` · ${o.unit_label}`:''}</p></div><span className={`orderStatus order-${o.status}`}>{orderStatusLabels[o.status]||o.status}</span><div className="orderRowActions"><a href={`/api/work-orders/${o.id}/pdf`} target="_blank" rel="noreferrer">PDF</a><button onClick={()=>onSelectCase(o.case_id)}>Vorgang →</button></div></article>):<div className="emptyCard workspaceEmpty">Noch keine Arbeitsaufträge vorhanden. Öffne einen Mangel und beauftrage dort einen Dienstleister.</div>}</div></div>;
}

function WorkOrderPanel({caseId}){
  const [data,setData]=useState(null); const [show,setShow]=useState(false); const [error,setError]=useState(''); const [busy,setBusy]=useState(false); const [result,setResult]=useState(null);
  const [form,setForm]=useState({providerId:'',title:'',description:'',dueOn:''});
  async function load(){try{setData(await api(`/api/cases/${caseId}/work-orders`))}catch(e){setData({orders:[],providers:[]})}} useEffect(()=>{load()},[caseId]);
  if(!data || (!data.providers.length&&!data.orders.length)) return data&&data.providers.length===0?<section className="contentCard contractorEmpty"><div className="cardKicker">DIENSTLEISTER</div><h3>Noch keine Partnerfirma hinterlegt</h3><p className="muted">Lege zuerst unter „Dienstleister“ eine Firma an, danach kannst du aus diesem Mangel einen Arbeitsauftrag erstellen.</p></section>:null;
  async function create(e){e.preventDefault();setBusy(true);setError('');setResult(null);try{const d=await api(`/api/cases/${caseId}/work-orders`,{method:'POST',body:JSON.stringify(form)});setResult(d);setShow(false);setForm({providerId:'',title:'',description:'',dueOn:''});await load()}catch(x){setError(x.message)}finally{setBusy(false)}}
  return <section className="contentCard workOrderPanel"><div className="sectionTitle"><div><div className="cardKicker">ARBEITSAUFTRÄGE</div><h3>Dienstleister beauftragen</h3><p className="muted">Auftrag als PDF und – bei eingerichtetem SMTP – direkt per E-Mail mit persönlichem Rückmeldelink senden.</p></div><button className="secondaryButton" onClick={()=>setShow(true)}>+ Arbeitsauftrag</button></div>{result&&<div className="successBox">Arbeitsauftrag erstellt. {result.delivery==='email'?'E-Mail wurde versendet.':'SMTP ist noch nicht aktiv – Link kann manuell geteilt werden.'}</div>}<div className="caseOrders">{data.orders.length?data.orders.map(o=><div className="caseOrder" key={o.id}><div><span>{o.trade}</span><b>{o.company_name}</b><small>{o.title}</small></div><span className={`orderStatus order-${o.status}`}>{orderStatusLabels[o.status]||o.status}</span><a href={`/api/work-orders/${o.id}/pdf`} target="_blank" rel="noreferrer">PDF</a></div>):<div className="emptyMini">Noch kein Dienstleister beauftragt.</div>}</div>{show&&<div className="modalBackdrop" onMouseDown={()=>setShow(false)}><div className="modal proModal" onMouseDown={e=>e.stopPropagation()}><div className="modalHeader"><div><div className="eyebrow">ARBEITSAUFTRAG</div><h2>Dienstleister beauftragen</h2></div><button className="iconButton" onClick={()=>setShow(false)}>×</button></div><form className="caseForm" onSubmit={create}><label>Dienstleister<select required value={form.providerId} onChange={e=>setForm({...form,providerId:e.target.value})}><option value="">Firma auswählen…</option>{data.providers.map(p=><option key={p.id} value={p.id}>{p.company_name} · {p.trade}</option>)}</select></label><label>Auftragstitel<input required placeholder="z. B. Heizungsanlage prüfen und instand setzen" value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/></label><label>Aufgabenbeschreibung<textarea required rows="6" placeholder="Was soll geprüft bzw. ausgeführt werden?" value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/></label><label>Gewünschte Erledigung <em>optional</em><input type="date" value={form.dueOn} onChange={e=>setForm({...form,dueOn:e.target.value})}/></label>{error&&<div className="errorBox">{error}</div>}<div className="modalActions"><button type="button" className="secondaryButton" onClick={()=>setShow(false)}>Abbrechen</button><button className="primaryButton" disabled={busy}>{busy?'Erstellen…':'Auftrag erstellen & senden'}</button></div></form></div></div>}</section>;
}

function ContractorPortal({token,navigate}){
  const [data,setData]=useState(null); const [error,setError]=useState(''); const [busy,setBusy]=useState(false); const [note,setNote]=useState(''); const [scheduledFor,setScheduledFor]=useState('');
  async function load(){try{setData(await api(`/api/contractor/work-orders/${token}`))}catch(e){setError(e.message)}} useEffect(()=>{load()},[token]);
  async function setStatus(status){setBusy(true);setError('');try{await api(`/api/contractor/work-orders/${token}/status`,{method:'POST',body:JSON.stringify({status,note,scheduledFor:status==='scheduled'?scheduledFor:null})});setNote('');await load()}catch(e){setError(e.message)}finally{setBusy(false)}}
  return <div className="contractorPortal"><header><Logo inverse/><span>EXTERNER ARBEITSAUFTRAG</span></header><main>{error?<div className="contractorError"><h1>Arbeitsauftrag nicht verfügbar</h1><p>{error}</p></div>:!data?<div className="contractorLoading">Arbeitsauftrag wird geladen…</div>:<><div className="contractorHero"><div><span>{data.order.trade}</span><h1>{data.order.title}</h1><p>Auftraggeber: <b>{data.order.organization_name}</b> · Auftragnehmer: <b>{data.order.company_name}</b></p></div><span className={`orderStatus order-${data.order.status}`}>{orderStatusLabels[data.order.status]||data.order.status}</span></div><div className="contractorGrid"><section><h3>Aufgabenbeschreibung</h3><p className="contractorDescription">{data.order.description}</p><dl><dt>Objekt</dt><dd>{data.order.property_name||data.order.property_label||'—'}</dd><dt>Einheit / Raum</dt><dd>{[data.order.unit_label,data.order.location_label].filter(Boolean).join(' · ')||'—'}</dd><dt>Adresse</dt><dd>{[data.order.property_street,[data.order.property_postal_code,data.order.property_city].filter(Boolean).join(' ')].filter(Boolean).join(', ')||'—'}</dd><dt>Gewünschte Erledigung</dt><dd>{fmtDate(data.order.due_on)}</dd></dl></section><aside><h3>Rückmeldung</h3><p>Bitte aktualisieren Sie den Auftrag direkt hier. Dafür ist kein MängelFix-Konto erforderlich.</p><label>Notiz<textarea rows="4" value={note} onChange={e=>setNote(e.target.value)} placeholder="z. B. Ersatzteil bestellt…"/></label><label>Termin<input type="datetime-local" value={scheduledFor} onChange={e=>setScheduledFor(e.target.value)}/></label><div className="contractorActions"><button disabled={busy} onClick={()=>setStatus('accepted')}>Auftrag annehmen</button><button disabled={busy||!scheduledFor} onClick={()=>setStatus('scheduled')}>Termin bestätigen</button><button disabled={busy} className="complete" onClick={()=>setStatus('completed')}>Als erledigt melden</button><button disabled={busy} className="decline" onClick={()=>setStatus('declined')}>Auftrag ablehnen</button></div>{data.order.contractor_note&&<div className="lastContractorNote"><b>Letzte Rückmeldung</b><p>{data.order.contractor_note}</p></div>}</aside></div></>}</main><footer>Dieser Link gewährt ausschließlich Zugriff auf den angezeigten Arbeitsauftrag.</footer></div>;
}

function Workspace({ user, setUser, onLogout, navigate }) {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showNew, setShowNew] = useState(false);
  const [selected, setSelected] = useState(null);
  const [view, setView] = useState('overview');
  const [management,setManagement]=useState(undefined);
  const [unreadNotifications,setUnreadNotifications]=useState(0);
  async function refreshUnread(){try{const d=await api('/api/notifications');setUnreadNotifications(d.unread||0);}catch{setUnreadNotifications(0)}}

  async function loadCases() {
    try { const data = await api('/api/cases'); setCases(data.cases); setError(''); }
    catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }
  useEffect(() => { loadCases(); refreshUnread(); api('/api/management/overview').then(setManagement).catch(()=>setManagement({organization:null})); const params=new URLSearchParams(window.location.search); const caseId=params.get('case'); if(caseId)setSelected(caseId); }, []);
  const profileComplete = Boolean(user.street && user.postalCode && user.city);
  const goProfile = () => { setSelected(null); setView('profile'); };

  let content;
  if (selected) content = <CaseDetail caseId={selected} onBack={() => setSelected(null)} onUpdated={loadCases} user={user} onProfile={goProfile} />;
  else if (loading) content = <div className="workspacePage"><div className="emptyCard">Vorgänge werden geladen…</div></div>;
  else if (view === 'overview') content = management?.organization ? <ManagementOverview user={user} cases={cases} onNew={() => setShowNew(true)} onSelect={setSelected} setView={setView} management={management} /> : <OverviewView user={user} cases={cases} onNew={() => setShowNew(true)} onSelect={setSelected} setView={setView} />;
  else if (view === 'cases') content = <CasesView cases={cases} onNew={() => setShowNew(true)} onSelect={setSelected} />;
  else if (view === 'objects') content = management?.organization ? <ManagedObjectsView onSelect={setSelected} /> : <ObjectsView cases={cases} onSelect={setSelected} />;
  else if (view === 'deadlines') content = <DeadlinesView cases={cases} onSelect={setSelected} />;
  else if (view === 'documents') content = <DocumentsView cases={cases} profileComplete={profileComplete} onProfile={goProfile} />;
  else if (view === 'providers') content = <ProvidersView />;
  else if (view === 'orders') content = <WorkOrdersView onSelectCase={setSelected} />;
  else if (view === 'notifications') content = <NotificationsView onSelect={setSelected} refreshUnread={refreshUnread} />;
  else if (view === 'audit') content = <AuditView />;
  else if (view === 'team') content = <TeamView />;
  else content = <ProfileView user={user} onSaved={setUser} />;

  return <div className="workspaceShell"><aside className="workspaceSidebar"><button className="sidebarBrand" onClick={() => setView('overview')}><Logo inverse /></button><div className="sidebarLabel">ARBEITSBEREICH</div><nav><button className={view === 'overview' && !selected ? 'active' : ''} onClick={() => { setSelected(null); setView('overview'); }}><span>Ü</span>Übersicht</button><button className={view === 'cases' || selected ? 'active' : ''} onClick={() => { setSelected(null); setView('cases'); }}><span>M</span>Mängel <b>{cases.filter(x => x.status !== 'resolved').length}</b></button><button className={view === 'objects' ? 'active' : ''} onClick={() => { setSelected(null); setView('objects'); }}><span>O</span>Objekte</button><button className={view === 'deadlines' ? 'active' : ''} onClick={() => { setSelected(null); setView('deadlines'); }}><span>F</span>Fristen <b>{cases.filter(x => x.deadline_on && x.status !== 'resolved').length}</b></button><button className={view === 'documents' ? 'active' : ''} onClick={() => { setSelected(null); setView('documents'); }}><span>D</span>Dokumente</button>{management?.organization&&<><button className={view === 'providers' ? 'active' : ''} onClick={() => { setSelected(null); setView('providers'); }}><span>H</span>Dienstleister</button><button className={view === 'orders' ? 'active' : ''} onClick={() => { setSelected(null); setView('orders'); }}><span>A</span>Aufträge</button></>}<button className={view === 'notifications' ? 'active' : ''} onClick={() => { setSelected(null); setView('notifications'); }}><span>B</span>Benachrichtigungen {unreadNotifications>0&&<b>{unreadNotifications}</b>}</button>{management?.organization&&<button className={view === 'audit' ? 'active' : ''} onClick={() => { setSelected(null); setView('audit'); }}><span>A</span>Aktivitätsprotokoll</button>}<button className={view === 'team' ? 'active' : ''} onClick={() => { setSelected(null); setView('team'); }}><span>T</span>{management?.organization ? 'Team' : 'Verwaltung'}</button></nav><div className="sidebarBottom"><button className={view === 'profile' ? 'active' : ''} onClick={goProfile}><span>P</span>Profil {!profileComplete && <i />}</button><button onClick={() => navigate('/')}><span>↗</span>Startseite</button><div className="sidebarUser"><div>{user.name.slice(0, 1).toUpperCase()}</div><p><b>{user.name}</b><span>{user.email}</span></p><button onClick={onLogout} title="Abmelden">↪</button></div></div></aside><main className="workspaceMain"><div className="mobileWorkspaceBar"><Logo compact /><button onClick={() => setShowNew(true)}>+ Neuer Mangel</button></div>{error && <div className="workspaceGlobalError">{error}</div>}{content}</main>{showNew && <NewCase onClose={() => setShowNew(false)} onCreated={created => { setShowNew(false); loadCases(); setSelected(created.id); }} />}</div>;
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
  if (path.startsWith('/einladung/')) return <InvitationPage token={path.split('/').pop()} user={state.user} navigate={navigate} />;
  if (path.startsWith('/auftrag/')) return <ContractorPortal token={path.split('/').pop()} navigate={navigate} />;
  if (path === '/anmelden') return <Auth mode="login" onSignedIn={user => setState({ loading: false, user })} navigate={navigate} />;
  if (path === '/registrieren') return <Auth mode="register" onSignedIn={user => setState({ loading: false, user })} navigate={navigate} />;
  if (path.startsWith('/app')) {
    if (!state.user) return <Auth mode="login" onSignedIn={user => setState({ loading: false, user })} navigate={navigate} />;
    return <Workspace user={state.user} setUser={user => setState({ loading: false, user })} onLogout={logout} navigate={navigate} />;
  }
  return <Landing user={state.user} navigate={navigate} />;
}
