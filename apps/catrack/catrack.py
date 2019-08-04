"""Tracking the cat.

catrack:
  module: catrack
  class: CaTrack
"""
import pkgutil
from datetime import datetime
from typing import Any, Dict, Optional, Set

import adutils
import appdaemon.plugins.hass.hassapi as hass

APP_NAME = "CaTrack"
APP_ICON = "🐾"


class CaTrack(hass.Hass):  # type: ignore
    """Notifies about significant movement in the gardenlounge."""

    def initialize(self) -> None:
        """Set up configuration values & state listener."""
        self.app_config: Dict[str, Any] = dict()
        self.cat_name = str(self.args.get("cat_name", "Miezi"))
        self.app_config["notify_service"] = str(self.args.get("notify_service"))
        self.app_config["movement_threshold"] = int(
            self.args.get("movement_threshold", 3)
        )
        self.delay = int(self.args.get("delay", 15)) * 60
        self.app_config["device_tracker"] = f"device_tracker.{self.cat_name.lower()}"

        # sensors/triggers
        cat_flap_sensors = set(self.args.get("cat_flap_sensors", set()))
        vibration_sensors = set(self.args.get("vibration_sensors", set()))
        person_sensors = set(self.args.get("person_sensors", set()))
        self.vibration_sensors: Set[str] = vibration_sensors
        self.sensors: Set[str] = set()
        self.sensors.update(cat_flap_sensors, vibration_sensors, person_sensors)

        self._handle = None
        self._handle_sybe = None

        # pre-filled attributes template
        self.base_attributes = dict(
            friendly_name=self.cat_name,
            icon="mdi:cat",
            last_movement=None,
            state_change=None,
            source_type=None,
        )

        if not self.sensors:
            return

        # xiaomi vibration sensor
        [
            self.listen_state(self.handler_gardenlounge, entity=sensor)
            for sensor in vibration_sensors
        ]

        # sure petcare catflap
        [
            self.listen_state(self.handler_cat_flap, entity=sensor)
            for sensor in cat_flap_sensors
        ]

        # when sensor is away, any movement must be the cat
        for sensor in person_sensors:
            self.listen_state(
                self.handler_sybe, entity=sensor, new="not_home", duration="180"
            )
            self.listen_state(self.handler_sybe, entity=sensor, new="home")

        adutils.show_info(
            self.log, APP_NAME, self.app_config, self.sensors, icon=APP_ICON
        )

    def state_change(self, location: str) -> bool:
        return not bool(self.get_state(self.app_config["device_tracker"]) == location)

    def last_changed(self, sensors: Set[str] = set()) -> Optional[str]:
        sensors = sensors or self.vibration_sensors
        relative_diff: str
        if not sensors and pkgutil.find_loader("pendulum"):
            import pendulum

            pendulum.set_locale("de")
            dt = min(
                [self.get_state(sensor, attribute="last_changed") for sensor in sensors]
            )
            relative_diff = pendulum.parse(dt).diff_for_humans()
        return relative_diff

    def handler_cat_flap(
        self,
        entity: str,
        attribute: Dict[str, Any],
        old: str,
        new: str,
        kwargs: Dict[str, Any],
    ) -> Optional[None]:
        """Handle state changes triggered by the cat flap."""
        self.log(f"triggered by {entity} | {old} -> {new}")

        # initialize trigger/location
        if new == "Inside" and old == "Outside":
            location = "home"
            icon = "mdi:home"
        elif new == "Outside" and old == "Inside":
            location = "not_home"
            icon = "mdi:tree"
        else:
            return

        state_change = self.state_change(location)

        # add trigger/location specific attributes to base attributes
        attributes: Dict[str, Any] = self.base_attributes
        attributes["source_type"] = "cat_flap"
        attributes["icon"] = icon
        attributes["state_change"] = state_change
        attributes["last_movement"] = str(datetime.now())
        attributes["last_movement_relative"] = self.last_changed()
        attributes["last_state"] = self.get_state(self.app_config["device_tracker"])
        attributes["catf_lap_state"] = new

        # update state
        self.cancel_timer(self._handle)

        self.set_state(
            self.app_config["device_tracker"], state=location, attributes=attributes
        )

        # notification
        if state_change:
            self.send_notification(
                attributes,
                location=location,
                message=f"Shivi ist {'wieder daheim 😽' if location == 'home' else 'jetzt draussen 😺'}",
            )
        else:
            self.log(
                f"  state '{self.get_state(self.app_config['device_tracker'])}' already set"
            )

    def handler_sybe(
        self,
        entity: str,
        attribute: Dict[str, Any],
        old: str,
        new: str,
        kwargs: Dict[str, Any],
    ) -> Optional[None]:
        """Handle state changes triggered by people."""
        self.log(f"triggered by {entity} | {old} -> {new}")

        if old == "unknown" or new == "unknown":
            return

        if entity == "binary_sensor.motion_all":
            # initialize trigger/location
            location = "home"
            state_change = self.state_change(location)

            # add trigger/location specific attributes to base attributes
            attributes: Dict[str, Any] = self.base_attributes
            attributes["source_type"] = "motion"
            attributes["state_change"] = state_change
            attributes["last_movement"] = str(datetime.now())
            attributes["last_movement_relative"] = self.last_changed()
            attributes["last_state"] = self.get_state(self.app_config["device_tracker"])
            attributes["trigger_entity"] = entity

            # update state
            self.cancel_timer(self._handle)
            self.set_state(
                self.app_config["device_tracker"], state=location, attributes=attributes
            )

            # notification
            if state_change:
                self.send_notification(
                    attributes, location=location, message=f"Shivi ist wieder daheim 😽"
                )
            else:
                self.log(
                    f"  state '{self.get_state(self.app_config['device_tracker'])}' already set",
                    ascii_encode=False,
                )

        # sybe arriving at home
        elif entity == "group.devices_sybe" and new == "home":
            self.cancel_listen_state(self._handle_sybe)

        # sybe leaving home
        elif entity == "group.devices_sybe" and new == "not_home":
            self._handle_sybe = self.listen_state(
                self.handler_sybe, entity="binary_sensor.motion_all"
            )

    def handler_gardenlounge(
        self,
        entity: str,
        attribute: Dict[str, Any],
        old: Any,
        new: Any,
        kwargs: Dict[str, Any],
    ) -> Optional[None]:
        """Handle state changes triggered by sensors."""
        self.log(
            f"{APP_ICON} triggered by {entity} | {old} -> {new}", ascii_encode=False
        )

        if old == "unknown" or new == "unknown":
            return

        # initialize trigger/location
        location = "Garten Lounge"
        state_change = self.state_change(location)

        # calculate difference of received sensor values
        old = [abs(int(float(value))) for value in old.split(",")]
        new = [abs(int(float(value))) for value in new.split(",")]
        diff = int(
            sum([abs(old[idx] - new[idx]) for idx in range(len(old))]) / len(old)
        )
        # old_way_stupid_diff = abs((int(sum(old) / len(old))) - (int(sum(new) / len(new))))

        # reduce movement_threshold if a cat is already there / sleeping
        movement_threshold = (
            self.app_config["movement_threshold"]
            if state_change
            else int(self.app_config["movement_threshold"] / 2)
        )

        self.log(
            f"  {APP_ICON} {old} - {new} -> {diff} (>{movement_threshold}?)",
            ascii_encode=False,
        )

        if diff > movement_threshold:

            # add trigger/location specific attributes to base attributes
            attributes: Dict[str, Any] = self.base_attributes
            attributes["source_type"] = "sensor_vibration"
            attributes["icon"] = "mdi:castle"
            attributes["state_change"] = state_change
            attributes["last_movement"] = str(datetime.now())
            attributes["last_movement_relative"] = self.last_changed()
            attributes["last_state"] = self.get_state(self.app_config["device_tracker"])
            attributes["last_diff"] = diff
            attributes["movement_threshold"] = movement_threshold

            # update state
            self.cancel_timer(self._handle)
            self.set_state(
                self.app_config["device_tracker"], state=location, attributes=attributes
            )

            # schedule callback to change the state when no more movement is detected
            self._handle = self.run_in(
                self.set_away,
                self.delay,
                entity_id=self.app_config["device_tracker"],
                location="not_home",
                delay=self.delay,
            )
            self.log(
                f"{APP_ICON} self.run_in({self.set_away}, {self.delay}, {self.app_config['device_tracker']}, location='not_home', delay={self.delay})",
                ascii_encode=False,
            )

            # notification
            if state_change:
                self.send_notification(
                    attributes,
                    location=location,
                    message=f"Bewegung in Shivis Gartenlounge! 🐾",
                )
            else:
                self.log(
                    f"  {APP_ICON} state '{self.get_state(self.app_config['device_tracker'])}' already set",
                    ascii_encode=False,
                )

    def send_notification(
        self,
        attributes: Dict[str, Any],
        location: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        if self.app_config["notify_service"]:
            self.call_service(
                self.app_config["notify_service"].replace(".", "/"), message=message
            )
            self.log(
                f"{APP_ICON} {self.cat_name} changed from '{attributes['last_state']}' to '{location}', notifying {self.app_config['notify_service']}",
                ascii_encode=False,
            )

    def set_away(self, kwargs: Dict[str, Any]) -> None:
        entity_id = kwargs["entity_id"]
        location = kwargs["location"]
        delay = kwargs["delay"]
        self.cancel_timer(self._handle)
        self._handle = None
        attributes = self.base_attributes
        attributes["icon"] = "mdi:tree"
        self.set_state(entity_id, state=location, attributes=attributes)
        self.log(
            f"{APP_ICON} set_away: self.set_state({entity_id}, state={location}, attributes={attributes})",
            ascii_encode=False,
        )
        self.log(
            f"{APP_ICON} gardenlounge: no movement since {delay / 60} minutes, {entity_id} changed to '{location}'",
            ascii_encode=False,
        )
