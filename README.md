## Vogelring Analytics

Eine Streamlit-App zur Analyse von Vogelring-Beobachtungen auf Basis der Datei `sightings.csv`.

### Architektur: Datensätze und Use Cases

- **Datensätze (Datasets)**: enthalten Spaltenauswahl, Filter und eine Zeilen-Selektion (Ausschlüsse). Sie referenzieren immer die aktuelle `sightings.csv` und kopieren keine Daten. Persistiert als JSON-Config in `app/storage/datasets/*.json` mit Feldern `{ name, description, columns, filters, excluded_ids, id_field }`. UI unter `app/views/data_sets.py`. Gemeinsame Helfer in `app/util/datasets.py`.
- **Use Cases (Analyse-Seiten)**: eigenständige Seiten im Sidebar, die auf einem ausgewählten Datensatz arbeiten und spezifische Metriken/Charts/Maps rendern. Jede Seite kapselt UI+Logik in einer `render_*`-Funktion und nutzt gemeinsame Utilities (Datasets, Mapping, Dates).

### Voraussetzungen

- Python 3.12+
- Datei `sightings.csv` im Projektwurzelverzeichnis (Semikolon-separiert)

### Installation und Start

#### Lokale Entwicklung

1. Abhängigkeiten installieren

```bash
uv sync
```

2. App starten

```bash
uv run streamlit run app/app.py
```

#### Docker Deployment

**Lokale Entwicklung mit Docker:**
```bash
docker compose -f docker-compose.dev.yml up --build
```

**Produktion (z.B. auf Raspberry Pi):**
```bash
docker compose up --build
```

#### Konfiguration

Die App kann über Umgebungsvariablen konfiguriert werden:

- `SIGHTINGS_FILE_PATH`: Pfad zur CSV-Datei (Standard: `./sightings.csv` lokal, `/app/data/sightings.csv` in Docker)

**Produktionssetup:**
- CSV-Datei wird in `/mnt/ssd/data/shared/sightings.csv` erwartet
- Kann durch n8n-Workflows automatisch aktualisiert werden
- Streamlit erkennt Änderungen automatisch durch `@st.cache_data`

### Funktionen

- Datensatz-Builder mit Spaltenauswahl, Filter-Builder und Zeilen-Auswahl (ein-/ausschließen)
- Datensätze laden, bearbeiten, als Kopie speichern, löschen
- Keine Datenkopie: Datensätze spiegeln stets die aktuelle `sightings.csv` wider
- Ort & Saison-Analyse:
  - Kohorte definieren per Jahr, Art, Ort, Zeitraum und optionalem Status
  - Verteilung der Beobachtungen über Orte im Jahr
  - Zeitlicher Verlauf (Monate) der Kohorte
  - Karte der Beobachtungen (falls Koordinaten vorhanden)

### Use Case: Karte

- Seite: `Karte` im Sidebar (`app/views/map_usecase.py`).
- Nutzer wählt einen Datensatz; standardmäßig werden nur `included`-Zeilen verwendet (Umschalter verfügbar).
- Darstellung der Punkte per `pydeck` auf Basis von `lat`/`lon` (nicht Beringung).
- Farbmodi:
  - Kategorie: Auswahl einer kategorialen Spalte, eindeutige Farben pro Kategorie, Legende wird angezeigt.
  - Numerisch: Auswahl einer numerischen Spalte, kontinuierlicher Farbverlauf (Viridis-ähnlich) inkl. Bereichssteuerung und Legendenangaben.
- Performant umgesetzt über Vektordatensatz und clientseitiges WebGL-Rendering; minimaler DataFrame-Kopiebedarf.

### Use Case: Mauser-Analyse

- Seite: `Mauser-Analyse` im Sidebar (`app/views/moult_usecase.py`).
- Beantwortet die Frage: "Verbringen Ringvögel die an Ort X mausern den Rest des Jahres auch an Ort X, an einem anderen bekannten Ort, oder irgendwo anders (=keine Daten)?"
- Workflow:
  1. **Parameter definieren**: Jahr, Art, Mauserort (nach Häufigkeit sortiert)
  2. **Mausernde Vögel definieren**: Zeitraum (Monate) oder Status-Filter
  3. **Analyse**: Automatische Identifikation der mausernden Ringe und Verfolgung ihrer Bewegungen
- Ergebnisse:
  - Zusammenfassungstabelle mit Kategorisierung (am selben Ort, andere Orte, nur Mauserzeit)
  - Interaktive Balkendiagramme (klickbar für Detailansicht)
  - Zeitliche Verteilung der Beobachtungen
  - Detailtabellen mit Vogelring-Links
- Nutzt Session State für persistente Ergebnisse bei Chart-Interaktionen.

### Hinweise

- Alle UI-Texte sind auf Deutsch.
- Daten werden beim Laden typisiert (Datum, Bool, Koordinaten) und um `year`/`month` ergänzt.
- Für eigene Use Cases empfiehlt sich die Wiederverwendung von: `app/util/datasets.py`, `app/util/col_mapping.py`, `app/util/dates.py`.
