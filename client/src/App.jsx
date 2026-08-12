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

function Logo() {
  return (
    <div className="brand">
      <div className="brandMark">M</div>
      <div><strong>MängelFix</strong><span>Dokumentieren. Nachhalten. Erledigen.</span></div>
    </div>
  );
}

function Auth({ onSignedIn }) {
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ name: '', email: '', password: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true); setError('');
    try {
      const endpoint = mode === 'login' ? '/api/auth/login' : '/api/auth/register';
      const data = await api(endpoint, { method: 'POST', body: JSON.stringify(form) });
      onSignedIn(data.user);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return (
    <main className="authPage">
      <section className="authHero">
        <Logo />
        <div className="heroCopy">
          <div className="eyebrow">DEIN MANGEL. DEINE DOKUMENTATION.</div>
          <h1>Aus „da ist was kaputt“ wird ein sauber dokumentierter Vorgang.</h1>
          <p>Fotos, Beschreibung, Empfänger, Frist und Verlauf an einem Ort. MängelFix macht aus verstreuten Notizen einen nachvollziehbaren Fall.</p>
          <div className="heroSteps">
            <span><b>1</b> Mangel erfassen</span>
            <span><b>2</b> Bilder & Frist ergänzen</span>
            <span><b>3</b> Schreiben/PDF erzeugen</span>
          </div>
        </div>
      </section>
      <section className="authPanel">
        <div className="authCard">
          <div className="segmented">
            <button className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>Anmelden</button>
            <button className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>Konto erstellen</button>
          </div>
          <h2>{mode === 'login' ? 'Willkommen zurück' : 'MängelFix starten'}</h2>
          <p className="muted">Deine Fälle bleiben in deinem Konto gespeichert.</p>
          <form onSubmit={submit} className="formStack">
            {mode === 'register' && <label>Name<input required value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} autoComplete="name" /></label>}
            <label>E-Mail<input required type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} autoComplete="email" /></label>
            <label>Passwort<input required minLength="8" type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} /></label>
            {error && <div className="errorBox">{error}</div>}
            <button className="primaryButton" disabled={busy}>{busy ? 'Einen Moment…' : mode === 'login' ? 'Anmelden' : 'Konto erstellen'}</button>
          </form>
          <p className="legalHint">MängelFix unterstützt bei Dokumentation und Organisation und ersetzt keine Rechtsberatung.</p>
        </div>
      </section>
    </main>
  );
}

function NewCase({ onClose, onCreated }) {
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({ title: '', category: categories[0], description: '', propertyLabel: '', locationLabel: '', discoveredOn: today, recipientName: '', recipientEmail: '', recipientAddress: '', deadlineOn: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  function field(name, value) { setForm(current => ({ ...current, [name]: value })); }

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
      <div className="modal" onMouseDown={e => e.stopPropagation()}>
        <div className="modalHeader"><div><div className="eyebrow">NEUER FALL</div><h2>Mangel erfassen</h2></div><button className="iconButton" onClick={onClose}>×</button></div>
        <form onSubmit={submit} className="caseForm">
          <div className="formGrid two">
            <label>Titel<input required placeholder="z. B. Heizung bleibt kalt" value={form.title} onChange={e => field('title', e.target.value)} /></label>
            <label>Kategorie<select value={form.category} onChange={e => field('category', e.target.value)}>{categories.map(item => <option key={item}>{item}</option>)}</select></label>
          </div>
          <label>Was ist passiert?<textarea required rows="5" placeholder="Beschreibe den Mangel so konkret wie möglich…" value={form.description} onChange={e => field('description', e.target.value)} /></label>
          <div className="formGrid two">
            <label>Objekt<input placeholder="z. B. Wohnung Musterstraße 12" value={form.propertyLabel} onChange={e => field('propertyLabel', e.target.value)} /></label>
            <label>Raum / Ort<input placeholder="z. B. Badezimmer" value={form.locationLabel} onChange={e => field('locationLabel', e.target.value)} /></label>
            <label>Festgestellt am<input type="date" value={form.discoveredOn} onChange={e => field('discoveredOn', e.target.value)} /></label>
            <label>Gewünschte Rückmeldung bis<input type="date" value={form.deadlineOn} onChange={e => field('deadlineOn', e.target.value)} /></label>
          </div>
          <div className="subSection"><h3>Empfänger</h3><p className="muted">Optional – kann später ergänzt werden.</p></div>
          <div className="formGrid two">
            <label>Name / Firma<input value={form.recipientName} onChange={e => field('recipientName', e.target.value)} /></label>
            <label>E-Mail<input type="email" value={form.recipientEmail} onChange={e => field('recipientEmail', e.target.value)} /></label>
          </div>
          <label>Anschrift<textarea rows="2" value={form.recipientAddress} onChange={e => field('recipientAddress', e.target.value)} /></label>
          {error && <div className="errorBox">{error}</div>}
          <div className="modalActions"><button type="button" className="secondaryButton" onClick={onClose}>Abbrechen</button><button className="primaryButton" disabled={busy}>{busy ? 'Speichern…' : 'Mangel speichern'}</button></div>
        </form>
      </div>
    </div>
  );
}

function CaseDetail({ caseId, onBack, onUpdated }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [note, setNote] = useState('');

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

  if (!data) return <div className="page"><button className="backButton" onClick={onBack}>← Zurück</button><div className="emptyCard">{error || 'Fall wird geladen…'}</div></div>;
  const item = data.case;

  return (
    <div className="page detailPage">
      <button className="backButton" onClick={onBack}>← Alle Mängel</button>
      <div className="detailHeader">
        <div><div className="eyebrow">{item.category}</div><h1>{item.title}</h1><div className="metaLine"><span className={`status status-${item.status}`}>{statusLabels[item.status]}</span><span>Festgestellt: {fmtDate(item.discovered_on)}</span></div></div>
        <a className="primaryButton linkButton" href={`/api/cases/${item.id}/pdf`} target="_blank" rel="noreferrer">PDF erstellen</a>
      </div>
      {error && <div className="errorBox">{error}</div>}
      <div className="detailGrid">
        <section className="contentCard">
          <h3>Beschreibung</h3><p className="descriptionText">{item.description}</p>
          <div className="factsGrid">
            <div><span>Objekt</span><b>{item.property_label || '—'}</b></div>
            <div><span>Raum / Ort</span><b>{item.location_label || '—'}</b></div>
            <div><span>Rückmeldung bis</span><b>{fmtDate(item.deadline_on)}</b></div>
            <div><span>Empfänger</span><b>{item.recipient_name || 'Noch nicht hinterlegt'}</b></div>
          </div>
        </section>
        <aside className="contentCard actionCard">
          <h3>Status</h3>
          <select disabled={busy} value={item.status} onChange={e => changeStatus(e.target.value)}>{Object.entries(statusLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>
          <p className="muted small">Der Status wird automatisch im Verlauf protokolliert.</p>
        </aside>
      </div>
      <section className="contentCard">
        <div className="sectionTitle"><div><h3>Fotos & Belege</h3><p className="muted">Bis zu 5 Bilder pro Upload, jeweils maximal 10 MB.</p></div><label className="secondaryButton uploadButton">Bilder hinzufügen<input type="file" accept="image/*" multiple onChange={uploadImages} /></label></div>
        {data.attachments.length ? <div className="photoGrid">{data.attachments.map(file => <a key={file.id} href={`/api/attachments/${file.id}`} target="_blank" rel="noreferrer"><img src={`/api/attachments/${file.id}`} alt={file.original_name} /><span>{file.original_name}</span></a>)}</div> : <div className="emptyInline">Noch keine Bilder hinterlegt.</div>}
      </section>
      <section className="contentCard">
        <div className="sectionTitle"><div><h3>Verlauf</h3><p className="muted">Notizen und Statusänderungen bleiben nachvollziehbar.</p></div></div>
        <form className="noteForm" onSubmit={addNote}><input placeholder="Neue Notiz, z. B. Hausverwaltung telefonisch erreicht…" value={note} onChange={e => setNote(e.target.value)} /><button className="primaryButton" disabled={busy}>Notiz speichern</button></form>
        <div className="timeline">{data.events.map(event => <div className="timelineItem" key={event.id}><div className="timelineDot"/><div><b>{event.event_type === 'created' ? 'Fall erstellt' : event.event_type === 'status' ? 'Status geändert' : 'Notiz'}</b><p>{event.note}</p><span>{new Date(event.created_at).toLocaleString('de-DE')}</span></div></div>)}</div>
      </section>
    </div>
  );
}

function Dashboard({ user, onLogout }) {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showNew, setShowNew] = useState(false);
  const [selected, setSelected] = useState(null);

  async function loadCases() {
    try { const data = await api('/api/cases'); setCases(data.cases); setError(''); }
    catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }
  useEffect(() => { loadCases(); }, []);

  const counts = useMemo(() => ({ open: cases.filter(item => item.status !== 'resolved').length, resolved: cases.filter(item => item.status === 'resolved').length, deadlines: cases.filter(item => item.deadline_on && item.status !== 'resolved').length }), [cases]);

  if (selected) return <AppShell user={user} onLogout={onLogout}><CaseDetail caseId={selected} onBack={() => setSelected(null)} onUpdated={loadCases} /></AppShell>;

  return (
    <AppShell user={user} onLogout={onLogout}>
      <div className="page">
        <div className="welcomeRow"><div><div className="eyebrow">ÜBERSICHT</div><h1>Hallo {user.name.split(' ')[0]}, was müssen wir festhalten?</h1><p className="muted">Dokumentiere einen Mangel, bevor Details verloren gehen.</p></div><button className="primaryButton" onClick={() => setShowNew(true)}>+ Mangel erfassen</button></div>
        <div className="statGrid">
          <div className="statCard"><span>Offene Fälle</span><strong>{counts.open}</strong><small>brauchen noch Aufmerksamkeit</small></div>
          <div className="statCard"><span>Mit Frist</span><strong>{counts.deadlines}</strong><small>Rückmeldedatum hinterlegt</small></div>
          <div className="statCard"><span>Erledigt</span><strong>{counts.resolved}</strong><small>sauber abgeschlossen</small></div>
        </div>
        <div className="listHeader"><div><h2>Deine Mängel</h2><p className="muted">Zuletzt bearbeitete Fälle zuerst.</p></div></div>
        {error && <div className="errorBox">{error}</div>}
        {loading ? <div className="emptyCard">Fälle werden geladen…</div> : cases.length === 0 ? (
          <div className="emptyCard bigEmpty"><div className="emptyIcon">✓</div><h3>Noch kein Mangel erfasst</h3><p>Wenn etwas auffällt, hältst du hier Fotos, Beschreibung, Frist und Verlauf zusammen.</p><button className="primaryButton" onClick={() => setShowNew(true)}>Ersten Mangel erfassen</button></div>
        ) : <div className="caseList">{cases.map(item => <button className="caseRow" key={item.id} onClick={() => setSelected(item.id)}><div className="caseIcon">!</div><div className="caseMain"><div className="caseTop"><h3>{item.title}</h3><span className={`status status-${item.status}`}>{statusLabels[item.status]}</span></div><p>{item.property_label || item.location_label || item.category}</p><div className="caseMeta"><span>{item.category}</span><span>{item.attachment_count} Bild{item.attachment_count === 1 ? '' : 'er'}</span>{item.deadline_on && <span>Frist: {fmtDate(item.deadline_on)}</span>}</div></div><span className="chevron">›</span></button>)}</div>}
      </div>
      {showNew && <NewCase onClose={() => setShowNew(false)} onCreated={created => { setShowNew(false); loadCases(); setSelected(created.id); }} />}
    </AppShell>
  );
}

function AppShell({ user, onLogout, children }) {
  return <div className="appShell"><header><Logo /><nav><span>{user.email}</span><button onClick={onLogout}>Abmelden</button></nav></header>{children}<footer>© 2026 Kamilunavo · MängelFix · Dokumentation statt Zettelwirtschaft</footer></div>;
}

export default function App() {
  const [state, setState] = useState({ loading: true, user: null });

  useEffect(() => {
    api('/api/me').then(data => setState({ loading: false, user: data.user })).catch(() => setState({ loading: false, user: null }));
  }, []);

  async function logout() {
    try { await api('/api/auth/logout', { method: 'POST' }); } catch { /* session may already be gone */ }
    setState({ loading: false, user: null });
  }

  if (state.loading) return <div className="splash"><Logo /><div className="loader" /></div>;
  if (!state.user) return <Auth onSignedIn={user => setState({ loading: false, user })} />;
  return <Dashboard user={state.user} onLogout={logout} />;
}
