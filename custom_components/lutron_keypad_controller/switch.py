"""Switch platform — per-button active-scene indicators.

State ON  = this button's scene is the currently active scene.
State OFF = a different scene is active (or none).

Turning ON  → triggers the button's configured action (same as a physical press).
Turning OFF → no-op (another button's scene must be activated to change state).

State is driven by two sources (both are safe and non-conflicting):
  1. LutronKeypadsController._sync_leds   — called on every button event (physical or HA).
  2. _handle_led_state_change             — tracks physical lutron_caseta LED entity changes
                                            so HA switch reflects keypad LED state passively.

_sync_leds does NOT write to physical LED entities (the Lutron bridge manages those).
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    DOMAIN,
    CONF_KEYPAD_TYPE,
    KEYPAD_GENERIC,
    get_button_layout,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entities = [
        LutronButtonSwitch(hass, entry, btn["number"], btn["is_raise"], btn["is_lower"])
        for btn in get_button_layout(entry.data)
    ]
    async_add_entities(entities, True)


class LutronButtonSwitch(SwitchEntity):
    """Active-scene indicator for a single keypad button."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        btn_number: int,
        is_raise: bool,
        is_lower: bool,
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._btn_number = btn_number
        self._btn_key = str(btn_number)
        self._is_raise = is_raise
        self._is_lower = is_lower
        self._led_state: bool = False
        self._attr_unique_id = f"{entry.entry_id}_button_{btn_number}_led"

    # ── Identity ──────────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        cfg = self._entry.options.get("buttons", {}).get(self._btn_key, {})
        return cfg.get("label") or f"Button {self._btn_number}"

    @property
    def icon(self) -> str:
        if self._is_raise:
            return "mdi:arrow-up-circle"
        if self._is_lower:
            return "mdi:arrow-down-circle"
        return "mdi:circle-slice-8" if self._led_state else "mdi:circle-outline"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.title,
            manufacturer="Lutron",
            model=self._entry.data.get(CONF_KEYPAD_TYPE, KEYPAD_GENERIC)
                      .replace("_", " ").title(),
        )

    # ── State ─────────────────────────────────────────────────────────────────

    @property
    def is_on(self) -> bool:
        return self._led_state

    def update_led_state(self, is_on: bool) -> None:
        """Called by the controller when the active-scene state changes."""
        self._led_state = is_on
        self.async_write_ha_state()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def _get_controller(self):
        return self._hass.data.get(DOMAIN, {}).get(
            "entry_controllers", {}
        ).get(self._entry.entry_id)

    async def async_added_to_hass(self) -> None:
        ctrl = self._get_controller()
        if ctrl is None:
            _LOGGER.warning(
                "Button %d: controller not found in hass.data — "
                "switch will not respond to button presses",
                self._btn_number,
            )
            return

        ctrl.register_button_switch(self._btn_number, self)
        _LOGGER.debug(
            "Button %d registered with controller '%s'",
            self._btn_number, ctrl.name,
        )

        led_entity = ctrl._get_led_entity(self._btn_number)
        if led_entity:
            # Seed initial state from physical LED
            state = self.hass.states.get(led_entity)
            if state is not None:
                self._led_state = state.state == "on"
                _LOGGER.debug(
                    "Button %d: seeded initial state from '%s' → %s",
                    self._btn_number, led_entity, self._led_state,
                )

            # Track physical LED changes passively (read-only — we do not write to it)
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    [led_entity],
                    self._handle_led_state_change,
                )
            )
            _LOGGER.debug(
                "Button %d: tracking physical LED entity '%s'",
                self._btn_number, led_entity,
            )

    @callback
    def _handle_led_state_change(self, event: Any) -> None:
        """Physical lutron_caseta LED changed — mirror it on the HA switch."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        new_val = new_state.state == "on"
        if new_val != self._led_state:
            _LOGGER.debug(
                "Button %d: physical LED changed to %s — updating HA switch",
                self._btn_number, new_state.state,
            )
            self._led_state = new_val
            self.async_write_ha_state()

    # ── Actions ───────────────────────────────────────────────────────────────

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Trigger this button's configured action (same as a physical press)."""
        ctrl = self._get_controller()
        if ctrl is None:
            _LOGGER.warning(
                "Button %d: cannot turn on — controller not available",
                self._btn_number,
            )
            return

        btn_cfg = ctrl._buttons.get(self._btn_number)
        if btn_cfg is None:
            _LOGGER.debug(
                "Button %d: no action configured (action will be ignored)",
                self._btn_number,
            )
            return

        # Set state ON immediately so HA UI confirms the change without flickering.
        # _sync_leds will also call update_led_state after the dispatch completes.
        self._led_state = True
        self.async_write_ha_state()

        try:
            await ctrl._dispatch(self._btn_number, btn_cfg)
        except Exception as exc:
            _LOGGER.error(
                "Button %d: dispatch raised an exception: %s",
                self._btn_number, exc,
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """No-op — scene state is only cleared by activating a different scene."""
        pass
