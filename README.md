## Vogelring Analytics

Eine Streamlit-App zur Analyse von Vogelring-Beobachtungen auf Basis der Datei `sightings.csv`.

### Architektur: Views, Datensätze, Use Cases

- **Views (Daten-Ansichten)**: vordefinierte Konfigurationen aus Spaltenauswahl und Filtern. Persistiert als JSON in `app/storage/*.json`. UI unter `app/views/data_view.py`.
- **Datensätze (Datasets)**: Ergebnis einer View inkl. Zeilen-Selektion (Spalte `included`). Persistiert als Meta-JSON + CSV in `app/storage/datasets/`. UI unter `app/views/data_sets.py`. Gemeinsame Helfer in `app/util/datasets.py`.
- **Use Cases (Analyse-Seiten)**: eigenständige Seiten im Sidebar, die auf einem ausgewählten Datensatz arbeiten und spezifische Metriken/Charts/Maps rendern. Jede Seite kapselt UI+Logik in einer `render_*`-Funktion und nutzt gemeinsame Utilities (Datasets, Mapping, Dates).

### Voraussetzungen

- Python 3.12+
- Datei `sightings.csv` im Projektwurzelverzeichnis (Semikolon-separiert)

### Installation und Start

1. Abhängigkeiten installieren

```bash
uv sync
```

2. App starten

```bash
uv run streamlit run app/app.py
```

### Funktionen

- Daten-Tabelle mit Spaltenauswahl und Filtern (Art, Geschlecht, Status, Jahr, Ort, Ring-Substring)
- Filter-Konfigurationen als Profil speichern/laden/löschen (persistiert in `.vogelring_state/filters.json`)
- Eigene Diagramme (Balkendiagramm, Aggregation Anzahl)
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

### Hinweise

- Alle UI-Texte sind auf Deutsch.
- Daten werden beim Laden typisiert (Datum, Bool, Koordinaten) und um `year`/`month` ergänzt.
- Für eigene Use Cases empfiehlt sich die Wiederverwendung von: `app/util/datasets.py`, `app/util/col_mapping.py`, `app/util/dates.py`.
