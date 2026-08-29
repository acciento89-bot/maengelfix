from pathlib import Path

path = Path("client/src/App.jsx")
text = path.read_text(encoding="utf-8")
wid = "DE464473083-00001"

if wid in text:
    print("W-IdNr. already present; nothing to do.")
    raise SystemExit(0)

needle = "['Verantwortlich für Inhalte', <p>Piotr Kaminski, Anschrift wie oben.</p>],"
insertion = (
    "['Wirtschafts-Identifikationsnummer', "
    "<p>Wirtschafts-Identifikationsnummer gemäß § 139c AO: DE464473083-00001</p>],\n    "
)

if needle not in text:
    raise SystemExit("Imprint insertion point not found; refusing to modify App.jsx")

text = text.replace(needle, insertion + needle, 1)
path.write_text(text, encoding="utf-8")
print("Added W-IdNr. to MängelFix imprint.")
