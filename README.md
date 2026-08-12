# MängelFix

MängelFix hilft dabei, Mängel sauber zu dokumentieren, Fristen und Kommunikation zu organisieren und aus den erfassten Daten ein nachvollziehbares Schreiben bzw. PDF zu erstellen.

## Zielgruppe

- Mieterinnen und Mieter
- Eigentümerinnen und Eigentümer
- private Vermieter / kleine Verwaltungen

## MVP

1. Konto erstellen / anmelden
2. Objekt anlegen
3. Mangel erfassen
   - Titel
   - Kategorie
   - Beschreibung
   - Entdeckungsdatum
   - Fotos
   - optional betroffener Raum / Ort
4. Empfänger hinterlegen
5. gewünschte Frist und Erinnerung setzen
6. Schreiben aus den eingegebenen Daten erzeugen
7. PDF herunterladen / teilen
8. Status und Verlauf pflegen
   - Entwurf
   - versendet
   - Rückmeldung erhalten
   - in Bearbeitung
   - erledigt

> MängelFix ist ein Organisations- und Dokumentationstool und ersetzt keine Rechtsberatung.

## Technik

- Node.js / Express API
- PostgreSQL
- React + Vite Web-App
- Docker / Docker Compose
- Ziel-Domain: `https://maengelfix.kamilunavo.com`
- API-Healthcheck: `/api/health`

## Lokaler Start

```bash
cp .env.example .env
docker compose up --build
```

Danach: `http://localhost:3000`
