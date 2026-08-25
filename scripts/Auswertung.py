# -*- coding: utf-8 -*-
import pandas as pd
from datetime import datetime
import os

# NEU: InfluxDB Imports
from influxdb_client import InfluxDBClient
from influxdb_client.client.query_api import QueryApi
# sqlite3 und der Pfad db_path sind jetzt optional und können entfernt werden,
# falls InfluxDB die einzige Quelle ist. Ich lasse sie vorerst drin,
# falls du die Funktionalität umschalten möchtest.


class Auswertung:
    """
    Auswertung historischer Daten, jetzt wahlweise aus InfluxDB.
    Liefert konsistent DataFrames zurück.
    """

    def __init__(
        self,
        entity_id,
        source="influxdb",  # NEU: Steuerung der Datenquelle
        db_path="/config/home-assistant_v2.db",
        # InfluxDB Konfiguration
        influx_url="http://localhost:8086",  # Passe dies an deine URL an
        influx_token="YOUR_INFLUXDB_TOKEN",  # Dein Token
        influx_org="YOUR_ORG",  # Deine Organisation
        influx_bucket="home_assistant_data",  # Dein Quell-Bucket
    ):
        self.entity_id = entity_id
        self.source = source
        self.db_path = db_path
        self.df_statistics = pd.DataFrame()
        self.df_states = pd.DataFrame()

        # NEU: InfluxDB Konfiguration speichern
        self.influx_url = influx_url
        self.influx_token = influx_token
        self.influx_org = influx_org
        self.influx_bucket = influx_bucket

        self._load_data()  # Geänderte Startmethode
        self._convert_states_to_numeric()  # Konvertiert state-Spalte zu Float

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def log(self, msg):
        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} - {msg}")

    def _load_data(self):
        """Wählt die Lade-Methode basierend auf der Konfiguration."""
        if self.source == "influxdb":
            self.log(f"Lade Daten für {self.entity_id} aus InfluxDB...")
            # self._load_statistics_influx()
            self._load_states_influx()
        elif self.source == "sqlite":
            self.log(f"Lade Daten für {self.entity_id} aus SQLite...")
            # Importe müssen ggf. im Code wiederhergestellt werden, wenn SQLite
            # standardmäßig deaktiviert wird. Ich gehe davon aus, dass sqlite3 oben importiert ist.

            self._load_statistics_sqlite()  # Umbenannt
            self._load_states_sqlite()  # Umbenannt
        else:
            self.log(f"Ungültige Datenquelle: {self.source}")

    # -------------------------------------------------------------------------
    # INFLUXDB LOADERS (NEU)
    # -------------------------------------------------------------------------

    def _query_influx(self, query):
        """Stellt eine Verbindung her und führt eine Flux-Abfrage aus."""
        try:
            client = InfluxDBClient(
                url=self.influx_url, token=self.influx_token, org=self.influx_org
            )
            query_api = client.query_api()

            # Die Abfrage gibt ein DataFrame pro Tabelle zurück
            dfs = query_api.query_data_frame(org=self.influx_org, query=query)
            client.close()

            # Wenn nur eine Tabelle/ein DataFrame zurückkommt, verwende diesen
            if isinstance(dfs, list):
                if not dfs:
                    return pd.DataFrame()
                # Oft wird eine Liste zurückgegeben, wenn mehrere Tabellen da sind.
                # Wir konketenieren die Ergebnisse (falls z.B. mehrere Queries im Flux)
                return pd.concat(dfs, ignore_index=False)

            return dfs

        except Exception as e:
            self.log(f"Fehler bei InfluxDB Abfrage: {e}")
            return pd.DataFrame()

    def _load_states_influx(self):
        """Lädt Daten (state) für die Entity aus InfluxDB (Measurement: 'states')."""

        # Flux Query für das Measurement 'states'
        query = fr"""
        from(bucket: "{self.influx_bucket}")
          |> range(start: 0)
          |> filter(fn: (r) => r["entity_id"] == "{self.entity_id.replace('sensor.', '')}")
          |> filter(fn: (r) => r["_field"] == "value")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        """

        starttime = datetime.now()
        df = self._query_influx(query)

        if df.empty:
            self.log("Keine States-Daten aus InfluxDB geladen.")
            return

        # Umbenennung und Indexierung
        df = df.rename(columns={"_time": "last_updated_ts"})
        df = df.rename(columns={"value": "state"})
        df = df.set_index("last_updated_ts")

        # Sicherstellen, dass der Index vom Typ datetime ist
        df.index = pd.to_datetime(df.index)

        if df.index.tz is not None:
             df.index = df.index.tz_localize(None)

        print(
            f"_load_states_influx: {int((datetime.now() - starttime).total_seconds()) // 60:02d}:{int((datetime.now() - starttime).total_seconds()) % 60:02d}"
        )
        self.df_states = df

    # -------------------------------------------------------------------------
    # SQLITE LOADERS (Umbenannt)
    # -------------------------------------------------------------------------

    # ACHTUNG: Die ursprünglichen Methoden wurden umbenannt, damit sie nicht
    # mit den neuen Influx-Methoden in Konflikt stehen. Sie benötigen den Import
    # 'import sqlite3'.

    def _load_statistics_sqlite(self):
        """Lädt Daten (start_ts, mean, min, max) für die Entity."""
        import sqlite3

        query = f"""
            SELECT start_ts, mean, min, max
            FROM statistics
            WHERE metadata_id = (
                SELECT id
                FROM statistics_meta
                WHERE statistic_id = '{self.entity_id}'
            )
            ORDER BY start_ts
        """
        # print(query) # Auskommentiert für kürzere Ausgabe
        starttime = datetime.now()
        try:
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql(
                    query, conn, parse_dates=["start_ts"], index_col="start_ts"
                )
        except Exception as e:
            self.log(f"Fehler DB: {e}")
            return

        df = df.dropna(subset=["mean"])
        print(
            f"_load_statistics_sqlite: {int((datetime.now() - starttime).total_seconds()) // 60:02d}:{int((datetime.now() - starttime).total_seconds()) % 60:02d}"
        )
        self.df_statistics = df

    def _load_states_sqlite(self):
        """Lädt Daten (last_updated_ts, state) für die Entity."""
        import sqlite3

        query = f"""
            SELECT last_updated_ts, state
            FROM states
            WHERE metadata_id = (
                SELECT metadata_id
                FROM states_meta
                WHERE entity_id = '{self.entity_id}'
            )
            ORDER BY last_updated_ts
        """
        # print(query) # Auskommentiert für kürzere Ausgabe
        starttime = datetime.now()
        try:
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql(
                    query,
                    conn,
                    parse_dates=["last_updated_ts"],
                    index_col="last_updated_ts",
                )
        except Exception as e:
            self.log(f"Fehler DB: {e}")
            return

        df = df.dropna(subset=["state"])
        print(
            f"_load_states_sqlite: {int((datetime.now() - starttime).total_seconds()) // 60:02d}:{int((datetime.now() - starttime).total_seconds()) % 60:02d}"
        )
        self.df_states = df

    # ... (Alle anderen Methoden wie _convert_states_to_numeric, _get_df,
    #      summary, extreme_days etc. bleiben unverändert und funktionieren weiter) ...

    def _convert_states_to_numeric(self):
        """Versucht die 'state'-Spalte in df_states in einen numerischen Typ umzuwandeln."""
        if not self.df_states.empty:
            self.df_states["state"] = pd.to_numeric(
                self.df_states["state"], errors="coerce"
            )
            self.df_states = self.df_states.dropna(subset=["state"])

    def _get_df(self, data_source):
        # ... (Unverändert) ...
        if data_source == "statistics":
            return self.df_statistics
        elif data_source == "states":
            return self.df_states
        else:
            raise ValueError(
                "Ungültige data_source. Muss 'statistics' oder 'states' sein."
            )

    def _round_df(self, df):
        """Rundet alle numerischen Spalten eines DataFrames auf 2 Nachkommastellen."""
        if df.empty:
            return df
        # Nur numerische Spalten runden
        return (
            df.select_dtypes(include=["number"])
            .apply(lambda col: col.round(2))
            .join(df.select_dtypes(exclude=["number"]))
        )

    def _format_index_by_rule(self, df, rule):
        # ... (Unveränderte Methode, wie oben) ...
        idx = df.index

        # Jahr
        if rule in ("Y", "YS", "YE"):
            df.index = idx.year.astype(str)
            df.index.name = "Jahr"
            return df

        # Monat
        if rule in ("M", "MS", "ME"):
            df.index = idx.strftime("%Y-%m")
            df.index.name = "Monat"
            return df

        # Quartal
        if rule.startswith("Q"):
            df.index = [f"{d.year}-Q{((d.month - 1) // 3) + 1}" for d in idx]
            df.index.name = "Quartal"
            return df

        # Woche
        if rule.startswith("W"):
            df.index = [f"{d.year}-KW{d.isocalendar().week:02d}" for d in idx]
            df.index.name = "Woche"
            return df

        # Tag
        if rule == "D":
            df.index = idx.strftime("%Y-%m-%d")
            df.index.name = "Datum"
            return df

        # Fallback: ursprüngliches DatetimeFormat
        df.index = idx.strftime("%Y-%m-%d")
        return df

    # -------------------------------------------------------------------------
    # BASIC STATISTICS
    # -------------------------------------------------------------------------

    def count(self, data_source="statistics"):
        """Anzahl Messwerte für die angegebene Datenquelle."""
        df = self._get_df(data_source)
        if df.empty:
            return 0

        # Zählspalte bestimmen
        count_col = "mean" if data_source == "statistics" else "state"
        return int(df[count_col].count())

    def overall_mean(self, data_source="statistics"):
        """Gesamtdurchschnitt für die angegebene Datenquelle."""
        df = self._get_df(data_source)
        if df.empty:
            return None

        # Mittelwertspalte bestimmen
        mean_col = "mean" if data_source == "statistics" else "state"
        return float(df[mean_col].mean())

    def overall_minmax(self, data_source="statistics"):
        """Absolutes Minimum/Maximum über den gesamten Zeitraum als DataFrame."""
        df = self._get_df(data_source)
        if df.empty:
            return pd.DataFrame(columns=["min", "max"])

        # Spalten bestimmen
        if data_source == "statistics":
            min_col, max_col = "min", "max"
        else:  # states
            min_col, max_col = (
                "state",
                "state",
            )  # Für states ist die state Spalte der Min/Max Wert

        return pd.DataFrame(
            {
                "min": [round(float(df[min_col].min()), 2)],
                "max": [round(float(df[max_col].max()), 2)],
            }
        )

    # -------------------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------------------

    def summary(self, rule, data_source="statistics", index_format=True):
        """
        Dynamische Zusammenfassung für beliebige Resample-Regeln und Datenquellen.
        """
        df = self._get_df(data_source)
        if df.empty:
            return pd.DataFrame()

        prefix_map = {
            # ... (Unveränderte Zuordnung der Präfixe) ...
            "D": "daily",
            "W": "weekly",
            "W-MON": "weekly",
            "W-TUE": "weekly",
            "W-WED": "weekly",
            "W-THU": "weekly",
            "W-FRI": "weekly",
            "W-SAT": "weekly",
            "W-SUN": "weekly",
            "M": "monthly",
            "MS": "monthly",
            "ME": "monthly",
            "Q": "quarterly",
            "QS": "quarterly",
            "Q-DEC": "quarterly",
            "Q-MAR": "quarterly",
            "Q-JUN": "quarterly",
            "Q-SEP": "quarterly",
            "Y": "year",
            "YS": "year",
            "YE": "year",
            "H": "hourly",
            "T": "minutely",
            "min": "minutely",
            "S": "secondly",
            "SEASON": "season",
        }

        # Prefix bestimmen
        key = prefix_map.get(rule, rule.lower())

        # Anpassung der Aggregationsspalten basierend auf der Datenquelle
        if data_source == "statistics":
            agg_funcs = {
                f"{key}_min": ("min", "min"),
                f"{key}_max": ("max", "max"),
                f"{key}_mean": ("mean", "mean"),
            }
        elif data_source == "states":
            # Bei states aggregieren wir nur die 'state' Spalte
            agg_funcs = {
                f"{key}_min": ("state", "min"),
                f"{key}_max": ("state", "max"),
                f"{key}_mean": ("state", "mean"),
                f"{key}_count": (
                    "state",
                    "count",
                ),  # Optional: Anzahl der Messwerte hinzufügen
            }
        else:
            return pd.DataFrame()

        df_resampled = df.resample(rule).agg(**agg_funcs)

        df_resampled = self._round_df(df_resampled)

        return (
            self._format_index_by_rule(df_resampled, rule)
            if index_format
            else df_resampled
        )

    def split_month_year(self, df, value_column=None, use_month_name=True):
        # ... (Unveränderte Methode, funktioniert mit jedem DataFrame, das einen DatetimeIndex hat) ...
        if df.empty:
            return pd.DataFrame()

        # Falls mehrere Spalten: Standard: erste Spalte nehmen
        if value_column is None:
            value_column = df.columns[0]

        # Extrahiere Jahr + Monat
        df = df.copy()
        df["year"] = df.index.year
        df["month"] = df.index.month

        # Optional Monat als Namen ersetzen
        if use_month_name:
            df["month_name"] = df.index.strftime("%b")
            month_index = "month_name"
        else:
            month_index = "month"

        # Pivot: Monate als Index, Jahre als Spalten
        pivot = df.pivot_table(
            index=month_index, columns="year", values=value_column, aggfunc="first"
        )

        # Sortierung: Jan–Dez
        if use_month_name:
            order = [
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
            ]
            pivot = pivot.reindex(order)
        else:
            pivot = pivot.sort_index()

        return pivot

    # -------------------------------------------------------------------------
    # EXTREME DAYS
    # -------------------------------------------------------------------------

    def extreme_days(self, data_source="statistics"):
        """
        Liefert pro Jahr den kältesten und wärmsten Tag.
        Nutzt die `daily_min`/`daily_max`-Spalten aus der `summary`-Methode.
        """
        # Holen der täglichen Zusammenfassung, passt sich automatisch an die Quelle an
        daily = self.summary("D", data_source, index_format=False)
        if daily.empty:
            return pd.DataFrame()

        # Spaltennamen anpassen (state wird zu daily_min/max)
        if data_source == "statistics":
            min_col, max_col = "daily_min", "daily_max"
        else:  # states
            # Da states nur eine Spalte 'state' hat, werden hier alle Aggregationen
            # auf 'state' basieren, z.B. daily_min, daily_max, daily_mean
            min_col, max_col = "daily_min", "daily_max"

        # Jahr hinzufügen
        daily["year"] = daily.index.year

        rows = []

        # Pro Jahr Min/Max Tag bestimmen
        for year, group in daily.groupby("year"):
            # Sicherstellen, dass die Spalten existieren
            if min_col not in group.columns or max_col not in group.columns:
                self.log(
                    f"Fehlende Spalten für extreme_days in data_source: {data_source}"
                )
                continue

            cold_idx = group[min_col].idxmin()
            warm_idx = group[max_col].idxmax()

            rows.append(
                {
                    "Datum": cold_idx.date(),
                    f"{year}_min": round(float(group.loc[cold_idx, min_col]), 2),
                    f"{year}_max": None,
                }
            )

            rows.append(
                {
                    "Datum": warm_idx.date(),
                    f"{year}_min": None,
                    f"{year}_max": round(float(group.loc[warm_idx, max_col]), 2),
                }
            )

        # DataFrame erzeugen
        df = pd.DataFrame(rows)

        # Datum als Index verwenden
        df = df.groupby("Datum").first().sort_index()

        # Spalten sortieren
        cols_sorted = sorted(
            df.columns, key=lambda x: (x.split("_")[0], x.split("_")[1])
        )
        df = df[cols_sorted]

        return self._round_df(df)

    # -------------------------------------------------------------------------
    # EXCEL EXPORT
    # -------------------------------------------------------------------------

    def export_excel(self, filename=None):
        """Exportiert Rohdaten + Monats- + Jahresübersicht in eine Exceldatei."""
        # Exportieren Sie jetzt beide Quellen
        if self.df_statistics.empty and self.df_states.empty:
            self.log("Keine Daten für Export.")
            return

        filename = filename or f"{self.entity_id.replace('sensor.', '')}_report.xlsx"
        path = os.path.join("/config", "www", filename)

        with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
            # Statistics-Daten
            if not self.df_statistics.empty:
                self._round_df(self.df_statistics).to_excel(
                    writer, sheet_name="Rohdaten_Stats"
                )
                self.summary("ME", data_source="statistics").to_excel(
                    writer, sheet_name="Monate_Stats"
                )
                self.summary("YE", data_source="statistics").to_excel(
                    writer, sheet_name="Jahre_Stats"
                )
                self.extreme_days(data_source="statistics").to_excel(
                    writer, sheet_name="Extreme_Stats"
                )

            # States-Daten
            if not self.df_states.empty:
                self._round_df(self.df_states).to_excel(
                    writer, sheet_name="Rohdaten_States"
                )
                self.summary("ME", data_source="states").to_excel(
                    writer, sheet_name="Monate_States"
                )
                self.summary("YE", data_source="states").to_excel(
                    writer, sheet_name="Jahre_States"
                )
                self.extreme_days(data_source="states").to_excel(
                    writer, sheet_name="Extreme_States"
                )

        self.log(f"Excel exportiert: {path}")


if __name__ == "__main__":
    # 1. Beispiel: Laden aus InfluxDB (Standard)
    # WICHTIG: Ersetze die Platzhalter mit deinen echten InfluxDB-Daten!
    influx_config = {
        "influx_url": "http://10.0.2.12:8086",
        "influx_token": "mmLvq9wTOx3nOEtup0TdpHXaQnG9tthBNlXTDSzd6W-KQZZjR3jiEHWdomxtJ1w11JW36ZhpJUqU0po4eTe1Fg==",
        "influx_org": "e4e395810e62e6d5",
        "influx_bucket": "Hassio",
    }

    # Hier wird explizit InfluxDB als Quelle gewählt
    auswertung_influx = Auswertung(
        entity_id="sensor.aussenthermometer_temperatur",
        source="influxdb",
        **influx_config,
    )

    print("\n" + "=" * 16 + " INFLUXDB STATES " + "=" * 17)
    print(f"Anzahl States: {auswertung_influx.count('states')}")
    print("-" * 50)
    print("Monats-Summary States (Auszug):")
    print(auswertung_influx.summary("ME", data_source="states").head())
    print("=" * 50)

    auswertung_influx.export_excel("influx_report.xlsx")

    # 2. Beispiel: Laden aus SQLite (optional)
    # import sqlite3 # Muss für diesen Teil verfügbar sein
    # auswertung_sqlite = Auswertung("sensor.aussenthermometer_temperatur", source="sqlite")
    # print("\n" + "=" * 16 + " SQLITE STATES " + "=" * 17)
    # print(f"Anzahl States: {auswertung_sqlite.count('states')}")
    # print("=" * 50)
