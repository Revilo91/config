**Rollladensteuerung 2 – Home Assistant Blaupause**
- **Zweck:** Steuert einen Rollladen abhängig vom Zustand der Fensterkontakte und weiteren Bedingungen wie Beschattungsmodus, Tag/Nacht, PC-Nutzung, Filmeabend usw.
- **Input:** Auswahl des Rollladens (`cover`-Entität).

**Wichtige Logik und Bedingungen:**
- Prüft, ob Fenster/Tür offen oder geschlossen ist.
- Unterscheidet zwischen verschiedenen Raum- und Automatikmodi ("Beschattung Automatisch", "Manuell", "Erzwungen", "Aus" etc.).
- Berücksichtigt, ob Tag- oder Nachtmodus aktiv ist.
- Besondere Modi wie "Filmeabend" oder "PC-Beschattung" werden erkannt und führen zu spezifischen Aktionen.
- Unterscheidet auch, ob der Rollladen zur Fensterseite oder Türseite gehört und ob der PC-Modus für diesen Rollladen gilt.

**Auslöser (Triggers):**
- Fenster/Tür wird geöffnet oder geschlossen.
- Änderung von Richtungs- oder Beschattungssensoren (z.B. `binary_sensor.beschattung_alles`, `binary_sensor.beschattung_pc`).
- Wechsel von Schaltern oder Eingabewerten (z.B. Tag/Nacht-Modus, Beschattungshöhe, PC-Steckdose, Kino-Schalter).

**Aktionen:**
- Rollladen fährt in die jeweilige Position je nach Modus und Zustand:
  - Morgens: Rollladen fährt auf Nacht-Position, wenn Tag/Nacht-Modus nicht aktiv und "Morgens" Label gesetzt.
  - "Filmeabend": Rollladen wird geschlossen.
  - Tagsüber (Beschattungsmodus aktiv): Rollladen fährt auf Tag-Position, abhängig von Fenster/Tür-Status, PC-Modus, Richtung, und Automatik-Labels.
  - Nachts: Rollladen fährt auf Nacht-Position, wenn Fenster offen.
  - Tür offen: Rollladen wird geöffnet.
  - Nachts & geschlossen: Rollladen wird geschlossen.
  - Standard: Öffnet oder schließt den Rollladen abhängig vom Tag/Nacht-Modus und Raumschalter.

**Kernidee:**  
Der Rollladen fährt automatisch in verschiedene Positionen, abhängig von Fensterstatus, Tageszeit, Raum- und Automatikmodi, Spezialmodi (Filmeabend/PC), und weiteren Bedingungen. Die Logik ist modular und flexibel für verschiedene Szenarien ausgelegt.

**Vorteil:**  
Automatische und kontextbasierte Steuerung der Rollladen für Komfort, Energieersparnis und Sicherheit.