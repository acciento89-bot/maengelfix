from pathlib import Path
p=Path('client/src/App.jsx')
s=p.read_text()
s=s.replace("const categoriesForContext=context=>categoriesByContext[context]||categoriesByContext.other;","const categoriesForContext=context=>categoriesByContext[context]||categoriesByContext.other;\nconst allCategories=[...new Set(Object.values(categoriesByContext).flat())];",1)
s=s.replace("{categories.map(c=><option key={c}>{c}</option>)}</select><select value={form.context}","{(form.context?categoriesForContext(form.context):allCategories).map(c=><option key={c}>{c}</option>)}</select><select value={form.context}",1)
p.write_text(s)
