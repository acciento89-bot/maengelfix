from pathlib import Path
p=Path('client/src/App.jsx')
s=p.read_text()
old="const categories = ['Feuchtigkeit / Schimmel','Heizung / Warmwasser','Sanitär','Elektro','Fenster / Türen','Boden / Wand','Beschädigung','Fehlteil / unvollständig','Funktionsmangel','Qualitätsmangel','Falsche Lieferung / Ausführung','Lärm','Außenbereich','Sonstiges'];"
new="""const categoriesByContext={
 housing:['Feuchtigkeit / Schimmel','Heizung / Warmwasser','Sanitär','Elektro','Fenster / Türen','Boden / Wand','Lärm / Geräusche','Außenbereich','Beschädigung','Schädlingsbefall','Sonstiges'],
 delivery:['Transportschaden','Verpackung beschädigt','Falsche Lieferung','Fehlteil / unvollständig','Verspätete Lieferung','Nicht geliefert','Zustellung / Ablage fehlerhaft','Sonstiges'],
 product:['Funktionsmangel','Qualitätsmangel','Beschädigung','Fehlteil / unvollständig','Falsches Produkt / Variante','Material- / Verarbeitungsfehler','Software / Elektronik','Sonstiges'],
 service:['Fehlerhafte Ausführung','Unvollständige Leistung','Beschädigung durch Arbeiten','Termin / Verzögerung','Materialmangel','Abweichung vom Auftrag','Funktionsmangel','Sauberkeit / Nacharbeit','Sonstiges'],
 vehicle:['Motor / Antrieb','Bremsen','Fahrwerk / Lenkung','Elektrik / Elektronik','Karosserie / Lack','Innenraum / Ausstattung','Reifen / Räder','Klima / Heizung','Werkstatt- / Servicefehler','Geräusche / Vibrationen','Sonstiges'],
 travel:['Zimmer / Ausstattung','Sauberkeit / Hygiene','Lärm / Ruhestörung','Klima / Temperatur','Sanitär / Bad','Verpflegung','Buchung / gebuchte Leistung','Service / Personal','Sicherheit','Transport / Transfer','Sonstiges'],
 other:['Beschädigung','Funktionsmangel','Qualitätsmangel','Fehlteil / unvollständig','Falsche Ausführung','Termin / Verzögerung','Sonstiges']
};
const categories=categoriesByContext.housing;
const allCategories=[...new Set(Object.values(categoriesByContext).flat())];"""
if old not in s: raise SystemExit('categories block missing')
s=s.replace(old,new,1)
s=s.replace("category:categories[0]","category:categoriesByContext.housing[0]",1)
s=s.replace("onChange={e=>field('caseContext',e.target.value)}","onChange={e=>{const next=e.target.value;setForm(current=>({...current,caseContext:next,category:categoriesByContext[next][0]}));}}",1)
s=s.replace("{categories.map(item => <option key={item}>{item}</option>)}","{categoriesByContext[form.caseContext].map(item => <option key={item}>{item}</option>)}",1)
search="{categories.map(c=><option key={c}>{c}</option>)}</select><select value={form.context}"
s=s.replace(search,"{(form.context?categoriesByContext[form.context]:allCategories).map(c=><option key={c}>{c}</option>)}</select><select value={form.context}",1)
p.write_text(s)
