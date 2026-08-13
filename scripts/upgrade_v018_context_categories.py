from pathlib import Path
import json,re
root=Path('.')
app_p=root/'client/src/App.jsx'; server_p=root/'server/index.js'; pkg_p=root/'server/package.json'
app=app_p.read_text(); server=server_p.read_text(); pkg=json.loads(pkg_p.read_text())
pkg['version']='0.18.0'; pkg_p.write_text(json.dumps(pkg,ensure_ascii=False,indent=2)+'\n')
server=re.sub(r"version: '[^']+'","version: '0.18.0'",server,count=1)

old="const categories = ['Feuchtigkeit / Schimmel','Heizung / Warmwasser','Sanitär','Elektro','Fenster / Türen','Boden / Wand','Beschädigung','Fehlteil / unvollständig','Funktionsmangel','Qualitätsmangel','Falsche Lieferung / Ausführung','Lärm','Außenbereich','Sonstiges'];"
new="""const categoriesByContext={
  housing:['Feuchtigkeit / Schimmel','Heizung / Warmwasser','Sanitär','Elektro','Fenster / Türen','Boden / Wand','Lärm','Außenbereich','Schädlingsbefall','Sonstiges'],
  delivery:['Transportschaden','Verpackung beschädigt','Produkt beschädigt','Falsche Lieferung','Fehlteil / unvollständig','Lieferung verspätet','Sonstiges'],
  product:['Beschädigung','Funktionsmangel','Qualitätsmangel','Fehlteil / unvollständig','Falsches Produkt / Variante','Material- / Verarbeitungsfehler','Software / Firmware','Sonstiges'],
  service:['Ausführung mangelhaft','Leistung unvollständig','Beschädigung verursacht','Abweichung vom Auftrag','Funktionsmangel nach Ausführung','Termin / Verzögerung','Sonstiges'],
  vehicle:['Motor / Antrieb','Bremsen','Fahrwerk / Lenkung','Elektrik / Elektronik','Karosserie / Lack','Innenraum','Klima / Heizung','Reifen / Räder','Undichtigkeit','Werkstattleistung','Sonstiges'],
  travel:['Unterkunft / Zimmer','Sauberkeit / Hygiene','Ausstattung defekt / fehlt','Lärm','Klima / Heizung','Sanitär','Verpflegung','Transport / Transfer','Buchung / Leistung abweichend','Sicherheit','Sonstiges'],
  other:['Beschädigung','Funktionsmangel','Qualitätsmangel','Fehlteil / unvollständig','Falsche Lieferung / Ausführung','Sonstiges']
};
const categories=categoriesByContext.housing;
const categoriesForContext=context=>categoriesByContext[context]||categoriesByContext.other;"""
if old not in app: raise SystemExit('global categories declaration not found')
app=app.replace(old,new,1)

# Context switch changes category immediately to a valid category for the selected kind of defect.
old_ctx="onChange={e=>field('caseContext',e.target.value)}"
new_ctx="onChange={e=>{const next=e.target.value;setForm(current=>({...current,caseContext:next,category:categoriesForContext(next)[0]}));}}"
if old_ctx not in app: raise SystemExit('case context selector not found')
app=app.replace(old_ctx,new_ctx,1)

# Only the NewCase category selector becomes context-aware; other management/protocol selectors keep their appropriate generic/housing catalog.
old_select="<label>Kategorie<select value={form.category} onChange={e => field('category', e.target.value)}>{categories.map(item => <option key={item}>{item}</option>)}</select></label>"
new_select="<label>Kategorie<select value={form.category} onChange={e => field('category', e.target.value)}>{categoriesForContext(form.caseContext).map(item => <option key={item}>{item}</option>)}</select></label>"
if old_select not in app: raise SystemExit('new-case category selector not found')
app=app.replace(old_select,new_select,1)
app_p.write_text(app)

# Server-side catalog prevents invalid context/category combinations for newly created private cases.
anchor="const pricingCatalog={"
if 'const defectCategoriesByContext=' not in server:
    catalog=r'''const defectCategoriesByContext={
  housing:['Feuchtigkeit / Schimmel','Heizung / Warmwasser','Sanitär','Elektro','Fenster / Türen','Boden / Wand','Lärm','Außenbereich','Schädlingsbefall','Sonstiges'],
  delivery:['Transportschaden','Verpackung beschädigt','Produkt beschädigt','Falsche Lieferung','Fehlteil / unvollständig','Lieferung verspätet','Sonstiges'],
  product:['Beschädigung','Funktionsmangel','Qualitätsmangel','Fehlteil / unvollständig','Falsches Produkt / Variante','Material- / Verarbeitungsfehler','Software / Firmware','Sonstiges'],
  service:['Ausführung mangelhaft','Leistung unvollständig','Beschädigung verursacht','Abweichung vom Auftrag','Funktionsmangel nach Ausführung','Termin / Verzögerung','Sonstiges'],
  vehicle:['Motor / Antrieb','Bremsen','Fahrwerk / Lenkung','Elektrik / Elektronik','Karosserie / Lack','Innenraum','Klima / Heizung','Reifen / Räder','Undichtigkeit','Werkstattleistung','Sonstiges'],
  travel:['Unterkunft / Zimmer','Sauberkeit / Hygiene','Ausstattung defekt / fehlt','Lärm','Klima / Heizung','Sanitär','Verpflegung','Transport / Transfer','Buchung / Leistung abweichend','Sicherheit','Sonstiges'],
  other:['Beschädigung','Funktionsmangel','Qualitätsmangel','Fehlteil / unvollständig','Falsche Lieferung / Ausführung','Sonstiges']
};
function normalizeDefectContext(value){return Object.prototype.hasOwnProperty.call(defectCategoriesByContext,value)?value:'housing'}
function normalizeDefectCategory(context,value){const list=defectCategoriesByContext[context]||defectCategoriesByContext.other;return list.includes(value)?value:list[0]}

'''
    server=server.replace(anchor,catalog+anchor,1)

# In case creation, calculate context/category once and use the normalized values.
create_anchor="const title = cleanText(req.body.title, 160);\n    const description = cleanText(req.body.description, 6000);"
if create_anchor in server and 'const caseContext=normalizeDefectContext' not in server[server.find(create_anchor):server.find(create_anchor)+600]:
    server=server.replace(create_anchor,create_anchor+"\n    const caseContext=normalizeDefectContext(req.body.caseContext);\n    const caseCategory=normalizeDefectCategory(caseContext,cleanText(req.body.category,80));",1)
server=server.replace("cleanText(req.body.category, 80) || 'Sonstiges',","caseCategory,",1)
server=server.replace("['housing','delivery','product','service','vehicle','travel','other'].includes(req.body.caseContext)?req.body.caseContext:'housing',","caseContext,",1)
server_p.write_text(server)
print('v0.18 context-aware categories prepared')
