from pathlib import Path
p=Path('client/src/App.jsx'); a=p.read_text()

a=a.replace('MÄNGEL FESTHALTEN, BEVOR DETAILS VERLOREN GEHEN','MÄNGEL. BEWEISE. EIN KLARER VORGANG.',1)
a=a.replace('Aus einem Problem wird ein <em>sauber dokumentierter Vorgang.</em>','Mängel dokumentieren. <em>Egal, wo sie entstehen.</em>',1)
a=a.replace('Fotos, Beschreibung, Empfänger, Frist und Verlauf an einem Ort. MängelFix hilft dir, Mängel strukturiert festzuhalten und professionelle Unterlagen daraus zu erstellen.','Vom beschädigten Paket über die Werkstatt bis zum Mietmangel: Privat sammelst du Beweise und Unterlagen an einem Ort. Hausverwaltungen steuern zusätzlich Mieter, Zuständigkeiten, Termine und Dienstleister.',1)
a=a.replace('<div className="heroTrust"><span>✓</span> Keine Zettelwirtschaft <span>✓</span> PDF-Dokumentation <span>✓</span> Fristen & Verlauf</div>','<div className="heroTrust"><span>✓</span> Privat & Verwaltung <span>✓</span> Professionelle PDFs <span>✓</span> Gegenstelle braucht kein Konto</div>',1)
a=a.replace('<h3>Heizung bleibt kalt</h3>','<h3>Lieferung beschädigt angekommen</h3>',1)
a=a.replace('<small>Objekt</small><b>Wohnung Musterstraße</b>','<small>Produkt</small><b>Kaffeevollautomat · Bestellung #2481</b>',1)

problem='''        <section className="problemStrip">
          <div><strong>Ein Mangel.</strong><span>Nicht fünf Chats, drei Fotosammlungen und ein vergessener Zettel.</span></div>
          <div className="stripRule" />
          <div><strong>Ein Vorgang.</strong><span>Alles nachvollziehbar an einer Stelle.</span></div>
        </section>'''
if 'audienceSection' not in a:
    audience=problem+'''\n\n        <section className="audienceSection">
          <div className="sectionIntro"><span>ZWEI ARBEITSWEISEN · EIN MÄNGELFIX</span><h2>Für deinen eigenen Mangel. Oder für eine ganze Verwaltung.</h2><p>Privat ist MängelFix ein allgemeiner Mängelmanager. Der Verwaltungsbereich konzentriert sich vollständig auf Immobilien- und Mietmängel.</p></div>
          <div className="audienceGrid">
            <article className="privateAudience"><span>PRIVAT</span><h3>Du hast einen Mangel?</h3><p>Dokumentiere selbst – unabhängig davon, ob Händler, Werkstatt, Vermieter oder Hausverwaltung MängelFix nutzen.</p><div className="audienceChips"><b>Lieferung</b><b>Produkt</b><b>Wohnen</b><b>Werkstatt</b><b>Reise</b><b>Dienstleistung</b></div><ul><li>Empfänger einfach selbst eintragen</li><li>Fotos und Basis-PDF bereits in Free</li><li>Digitale Verwaltungsverknüpfung nur optional</li></ul></article>
            <article className="managementAudience"><span>HAUSVERWALTUNG</span><h3>Mängelprozesse statt Zettelwirtschaft.</h3><p>Vom Eingang der Mietermeldung bis zum erledigten Handwerkerauftrag.</p><div className="managementFlow"><b>Mieter</b><i>→</i><b>Mangel</b><i>→</i><b>Team</b><i>→</i><b>Dienstleister</b><i>→</i><b>Erledigt</b></div><ul><li>Objekte und Einheiten sauber zuordnen</li><li>Team, Fristen, Aufgaben und Termine</li><li>Arbeitsaufträge und Übergabeprotokolle</li></ul></article>
          </div>
        </section>'''
    if problem not in a: raise SystemExit('landing anchor missing')
    a=a.replace(problem,audience,1)

a=a.replace('Gebaut für echte Vorgänge, nicht für hübsche Demo-Karten.','Ein Werkzeug für den kompletten Mängelverlauf.',1)
a=a.replace('Heizung bleibt kalt <b>OFFEN</b>','Paket beschädigt <b>OFFEN</b>',1)
a=a.replace('Fenster undicht <b>VERSENDET</b>','Werkstatt-Nachbesserung <b>VERSENDET</b>',1)
a=a.replace('Armatur defekt <b>ERLEDIGT</b>','Mietmangel Bad <b>ERLEDIGT</b>',1)
a=a.replace('<li>Bis zu 5 aktive Vorgänge</li>','<li>Bis zu 5 aktive Vorgänge</li><li>Bis zu 3 Fotos je Vorgang</li>',1)
a=a.replace('<li>Unbegrenzte Vorgänge</li>','<li>Unbegrenzte aktive Vorgänge</li>',1)
a=a.replace(">Fristen <b>{cases.filter(x => x.deadline_on && x.status !== 'resolved').length}</b></button>",">Fristen <b>{cases.filter(x => x.deadline_on && x.status !== 'resolved').length}</b>{!management?.organization&&!hasPro&&<i className=\"proNavTag\">PRO</i>}</button>",1)
p.write_text(a)
print('v0.19 landing prepared')
