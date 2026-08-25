from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from datetime import timedelta
# from homeassistant.helpers.template import Template


class RolladenSteuerung:
    def __init__(self, hass, rollladen_id):
        self.hass = hass
        self.rollladen_id = rollladen_id

    def get_state(self, entity_id, attribute=None):
        """Holt den Zustand einer Entität und gibt das Attribut zurück, falls angegeben."""
        # state = self.hass.states.get(entity_id)
        # if not state:
        #     return None
        # if attribute:
        #     return state.attributes.get(attribute)
        return getattr(self.hass.states.get(entity_id), 'attributes', {}).get(attribute, None)

    def trigger_conditions(self):
        """Überprüft die Trigger-Bedingungen für das Öffnen oder Schließen des Rolladens."""
        # Überprüfen der standardmäßigen Trigger-Bedingungen (Fenster und Richtung)
        direction = self.get_state(self.rollladen_id, "direction")
        if not direction:
            return False

        window_state = self.get_state(self.rollladen_id, "window")

        # Trigger Bedingungen: Fensterstatus und Richtung (offen/geschlossen)
        basic_conditions = any(
            [
                window_state == STATE_ON,
                window_state == STATE_OFF,
                self.hass.states.is_state(
                    f"binary_sensor.richtung{direction}", STATE_ON
                ),
                self.hass.states.is_state(
                    f"binary_sensor.richtung{direction}pc", STATE_ON
                ),
                self.hass.states.is_state(
                    f"binary_sensor.richtung{direction}", STATE_OFF
                ),
                self.hass.states.is_state(
                    f"binary_sensor.richtung{direction}pc", STATE_OFF
                ),
            ]
        )

        # Weitere Trigger für spezifische Entitäten
        additional_conditions = any(
            [
                # Trigger für binary_sensor.beschattung_pc und binary_sensor.beschattung_alles
                self.hass.states.is_state("binary_sensor.beschattung_pc", STATE_ON),
                self.hass.states.is_state("binary_sensor.beschattung_alles", STATE_ON),
                self.hass.states.is_state("binary_sensor.beschattung_pc", STATE_OFF),
                self.hass.states.is_state("binary_sensor.beschattung_alles", STATE_OFF),
                # Trigger für Zeitverzögerung (for: 00:03:00)
                self.hass.states.is_state("binary_sensor.beschattung_pc", STATE_ON)
                and self.hass.states.get("binary_sensor.beschattung_pc").last_updated
                < timedelta(minutes=3),
                self.hass.states.is_state(
                    "input_select.beschattung_automatik", STATE_ON
                ),
                self.hass.states.is_state("input_boolean.tag_nacht_modus", STATE_ON),
                self.hass.states.is_state(
                    "input_boolean.rolllade_ankleide_morgens_auf", STATE_ON
                ),
                self.hass.states.is_state("switch.eg_buro_schaltsteckdose", STATE_ON),
                self.hass.states.is_state("switch.filmeabend", STATE_ON),
                self.get_state("input_number.beschattungshohe_tag") is not None,
                self.get_state("input_number.beschattungshohe_nacht") is not None,
            ]
        )

        # Kombinierte Triggerbedingungen
        return basic_conditions or additional_conditions

    def set_cover_position(self, position: int):
        """Setzt die Position des Rolladens."""
        self.hass.services.call(
            COVER_DOMAIN,
            "set_cover_position",
            {"entity_id": self.rollladen_id, "position": position},
        )

    def main_action(self):
        """Hauptaktion für die Steuerung des Rolladens basierend auf verschiedenen Bedingungen."""
        # Bessere Lesbarkeit durch Aufteilen der Bedingungen
        tag_nacht_modus = self.get_state("input_boolean.tag_nacht_modus")
        beschattungshohe_nacht = self.get_state("input_number.beschattungshohe_nacht")
        beschattungshohe_tag = self.get_state("input_number.beschattungshohe_tag")
        filmeabend = self.get_state("switch.filmeabend")

        if tag_nacht_modus == STATE_OFF:
            # Morgens, wenn "Ankleide" aktiviert
            if "morgens" in self.rollladen_id and self.hass.states.is_state(
                "input_boolean.rolllade_ankleide_morgens_auf", STATE_ON
            ):
                self.set_cover_position(int(beschattungshohe_nacht))
        elif filmeabend == STATE_ON:
            # Filmeabend, Rolladen schließen
            if "filmeabend" in self.rollladen_id:
                self.hass.services.call(
                    COVER_DOMAIN, "close_cover", {"entity_id": self.rollladen_id}
                )
        else:
            # Beschattung logik
            window_state = self.get_state(self.rollladen_id, "window")
            direction_state = self.get_state(
                f"binary_sensor.richtung{self.get_state(self.rollladen_id, 'direction')}"
            )
            if window_state == STATE_ON:
                if direction_state == STATE_ON:
                    self.set_cover_position(int(beschattungshohe_tag))
                else:
                    self.set_cover_position(100)
            else:
                if tag_nacht_modus == STATE_ON:
                    self.set_cover_position(int(beschattungshohe_tag))
                else:
                    self.set_cover_position(0)

    def execute(self):
        """Führt die Hauptaktion aus, wenn die Trigger-Bedingungen erfüllt sind."""
        if self.trigger_conditions():
            self.main_action()
