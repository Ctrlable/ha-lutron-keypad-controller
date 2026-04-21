"""
Lutron Keypad Controller — custom component for Home Assistant
==============================================================

Listens for ``lutron_caseta_button_event`` events fired by the built-in
``lutron_caseta`` integration and routes them to configurable HA actions.

Supported keypads:
  SeeTouch · Hybrid SeeTouch · Sunnata · Hybrid Sunnata ·
  Alisee · Palladiom · Tabletop · Pico

Supported action types per button:
  stateful_scene  — activates an HA scene and tracks it as "active" on the keypad
                    (other buttons in the same group deactivate); LED feedback optional
  ha_scene        — plain HA scene, no state tracking
  automation      — triggers an automation
  script          — runs a script
  entity_toggle   — toggles one or more entities (lights, switches, etc.)
  cover_cycle     — cycles a cover: open → stop → close (repeatable)
  light_cycle_dim — cycles a light through dim levels: 100 % → 75 % → 50 % → 25 % → off
  raise           — raises shades OR brightens lights based on the last active action
  lower           — lowers shades OR dims lights based on the last active action
  none            — no-op placeholder

Configuration (add to configuration.yaml):

lutron_keypad_controller:
  keypads:
    - name: "Living Room Keypad"
      device_serial: "12345678"          # serial from Lutron, or match by device_name + area_name
      device_name: "Living Room"         # optional: used to match if serial not unique
      area_name: "Living Room"           # optional: used to match events
      keypad_type: sunnata               # one of: seetouch, seetouch_hybrid, sunnata,
                                         #   sunnata_hybrid, alisee, palladiom, tabletop, pico, generic
      scene_group: "living_room"         # optional: keypads sharing a group share stateful-scene state
      buttons:
        - button_number: 1
          label: "Movie"
          action_type: stateful_scene
          action_target: scene.living_room_movie
          led_entity: switch.living_room_keypad_led_1  # optional
        - button_number: 2
          label: "Bright"
          action_type: stateful_scene
          action_target: scene.living_room_bright
          led_entity: switch.living_room_keypad_led_2
        - button_number: 3
          label: "Off"
          action_type: ha_scene
          action_target: scene.living_room_off
        - button_number: 4
          label: "Shades Up"
          action_type: raise
          # no target needed — raise/lower act on the last active scene's covers/lights
        - button_number: 5
          label: "Shades Down"
          action_type: lower
        - button_number: 6
          label: "Fan Toggle"
          action_type: entity_toggle
          action_target:
            - fan.living_room_fan
        - button_number: 7
          label: "Dim Cycle"
          action_type: light_cycle_dim
          action_target:
            - light.living_room_cans
          action_params:
            levels: [100, 75, 50, 25]   # optional: override default dim levels
        - button_number: 8
          label: "Curtain Cycle"
          action_type: cover_cycle
          action_target:
            - cover.living_room_curtain
        - button_number: 9
          label: "Evening"
          action_type: automation
          action_target: automation.living_room_evening
        - button_number: 10
          label: "Party Script"
          action_type: script
          action_target: script.party_mode
          action_params:
            variables:
              room: living_room
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant, Event, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers import entity_platform, entity_registry as er, device_registry as dr
from homeassistant.const import (
    SERVICE_TURN_ON,
    SERVICE_TURN_OFF,
    SERVICE_TOGGLE,
    ATTR_ENTITY_ID,
)

from .const import (
    DOMAIN,
    LUTRON_EVENT,
    CONF_BUTTONS,
    CONF_BUTTON_NUMBER,
    CONF_BUTTON_LABEL,
    CONF_ACTION_TYPE,
    CONF_ACTION_TARGET,
    CONF_ACTION_PARAMS,
    CONF_LED_ENTITY,
    CONF_LED_INVERT,
    CONF_LED_MODE,
    LED_MODE_ROOM,
    LED_MODE_SCENE,
    CONF_DEVICE_SERIAL,
    CONF_DEVICE_NAME,
    CONF_AREA_NAME,
    CONF_KEYPAD_TYPE,
    ACTION_STATEFUL_SCENE,
    ACTION_HA_SCENE,
    ACTION_AUTOMATION,
    ACTION_SCRIPT,
    ACTION_ENTITY_TOGGLE,
    ACTION_COVER_CYCLE,
    ACTION_LIGHT_CYCLE_DIM,
    ACTION_RAISE,
    ACTION_LOWER,
    ACTION_NONE,
    DIM_CYCLE_LEVELS,
    COVER_STATE_OPEN,
    COVER_STATE_STOP,
    COVER_STATE_CLOSE,
    RAISE_LOWER_STEP,
    ATTR_ACTIVE_SCENE,
    ATTR_LAST_ACTION,
    ATTR_COVER_STATES,
    ATTR_LIGHT_DIM_STEPS,
    get_button_layout,
    get_button_list,
    KEYPAD_GENERIC,
)

_LOGGER = logging.getLogger(__name__)

# ── YAML schema ───────────────────────────────────────────────────────────────

BUTTON_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BUTTON_NUMBER): cv.positive_int,
        vol.Optional(CONF_BUTTON_LABEL, default=""): cv.string,
        vol.Required(CONF_ACTION_TYPE): vol.In(
            [
                ACTION_STATEFUL_SCENE,
                ACTION_HA_SCENE,
                ACTION_AUTOMATION,
                ACTION_SCRIPT,
                ACTION_ENTITY_TOGGLE,
                ACTION_COVER_CYCLE,
                ACTION_LIGHT_CYCLE_DIM,
                ACTION_RAISE,
                ACTION_LOWER,
                ACTION_NONE,
            ]
        ),
        vol.Optional(CONF_ACTION_TARGET): vol.Any(
            cv.entity_id, [cv.entity_id], cv.string
        ),
        vol.Optional(CONF_ACTION_PARAMS, default={}): dict,
        vol.Optional(CONF_LED_ENTITY): cv.entity_id,
    }
)

KEYPAD_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Optional(CONF_DEVICE_SERIAL, default=""): cv.string,
        vol.Optional(CONF_DEVICE_NAME, default=""): cv.string,
        vol.Optional(CONF_AREA_NAME, default=""): cv.string,
        vol.Optional(CONF_KEYPAD_TYPE, default="generic"): cv.string,
        vol.Optional("scene_group", default=""): cv.string,
        vol.Required(CONF_BUTTONS): vol.All(cv.ensure_list, [BUTTON_SCHEMA]),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required("keypads"): vol.All(cv.ensure_list, [KEYPAD_SCHEMA]),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS: list[str] = ["sensor", "switch", "select", "text"]


def _build_buttons_from_options(buttons_options: dict) -> list[dict]:
    """Convert options {"1": {…}, "2": {…}} to a list suitable for LutronKeypadsController."""
    result = []
    for btn_num_str, btn_data in buttons_options.items():
        try:
            btn_num = int(btn_num_str)
        except ValueError:
            continue
        if not btn_data.get("enabled", True):
            continue
        action_type = btn_data.get(CONF_ACTION_TYPE, ACTION_NONE)
        if not action_type or action_type == ACTION_NONE:
            continue
        btn_cfg: dict = {
            CONF_BUTTON_NUMBER: btn_num,
            CONF_BUTTON_LABEL:  btn_data.get(CONF_BUTTON_LABEL, ""),
            CONF_ACTION_TYPE:   action_type,
        }
        target = btn_data.get(CONF_ACTION_TARGET, "")
        if target:
            # Normalize: options flow stores lists; multi-entity actions keep
            # the list, single-entity actions get unwrapped to a plain string.
            if isinstance(target, list):
                flat = [t.strip() for t in target if str(t).strip()]
            elif isinstance(target, str) and "," in target:
                flat = [t.strip() for t in target.split(",") if t.strip()]
            else:
                flat = [target] if target else []

            if flat:
                if action_type in (ACTION_STATEFUL_SCENE, ACTION_HA_SCENE,
                                   ACTION_AUTOMATION, ACTION_SCRIPT):
                    btn_cfg[CONF_ACTION_TARGET] = flat[0]
                else:
                    btn_cfg[CONF_ACTION_TARGET] = flat
        if btn_data.get(CONF_LED_ENTITY):
            btn_cfg[CONF_LED_ENTITY] = btn_data[CONF_LED_ENTITY]
        if btn_data.get(CONF_LED_INVERT):
            btn_cfg[CONF_LED_INVERT] = True
        if btn_data.get("scene_group"):
            btn_cfg["scene_group"] = btn_data["scene_group"]
        if btn_data.get(CONF_LED_MODE):
            btn_cfg[CONF_LED_MODE] = btn_data[CONF_LED_MODE]
        result.append(btn_cfg)
    return result


# ── Shared scene-group state ───────────────────────────────────────────────────
# scene_groups[group_name] = button_number of the last activated stateful scene
_SCENE_GROUPS: dict[str, int | None] = {}


# ── LED entity auto-discovery ─────────────────────────────────────────────────

import re as _re

async def _find_led_entities(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[int, str]:
    """Scan the entity registry for lutron_caseta LED switch entities.

    Returns {button_number: entity_id}.  Manual led_entity config always
    overrides this map; the map is only used as an auto-discovery fallback.
    """
    serial    = str(config_entry.data.get(CONF_DEVICE_SERIAL, "")).strip()
    device_id = str(config_entry.data.get("device_id", "")).strip()

    _LOGGER.debug(
        "LED discovery starting for '%s' — serial=%s device_id=%s",
        config_entry.title, serial, device_id,
    )

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    _LOGGER.debug("LED discovery: %d devices in registry", len(dev_reg.devices))

    # Find the lutron_caseta HA device that matches our keypad
    lutron_device = None
    for device in dev_reg.devices.values():
        for ident_domain, identifier, *_ in device.identifiers:
            if ident_domain != "lutron_caseta":
                continue
            id_str = str(identifier).strip()
            if (serial and id_str == serial) or (device_id and id_str == device_id):
                lutron_device = device
                break
        if lutron_device:
            break

    if lutron_device is None:
        _LOGGER.warning(
            "LED discovery: no lutron_caseta device matched serial=%s device_id=%s. "
            "Dumping all device identifiers:",
            serial, device_id,
        )
        for device in dev_reg.devices.values():
            _LOGGER.warning(
                "  Device '%s': identifiers=%s",
                device.name, list(device.identifiers),
            )
        return {}

    all_entries = er.async_entries_for_device(ent_reg, lutron_device.id)
    _LOGGER.debug(
        "LED discovery: found lutron device '%s' (id=%s) with %d entities: %s",
        lutron_device.name, lutron_device.id, len(all_entries),
        [(e.entity_id, e.domain, e.unique_id) for e in all_entries],
    )

    led_map: dict[int, str] = {}
    for entry in all_entries:
        if entry.domain != "switch":
            continue
        haystack = " ".join(filter(None, [
            entry.name, entry.original_name, entry.unique_id
        ])).lower()
        _LOGGER.debug(
            "LED discovery: switch entity %s — haystack='%s'",
            entry.entity_id, haystack,
        )
        if "led" not in haystack:
            continue
        match = _re.search(r"button[_\s]+(\d+)[_\s]+led", haystack)
        if match:
            btn_num = int(match.group(1))
            led_map[btn_num] = entry.entity_id
            _LOGGER.debug(
                "LED discovery: button %d → %s", btn_num, entry.entity_id
            )
        else:
            _LOGGER.warning(
                "LED discovery: '%s' contains 'led' but button number "
                "regex did not match — haystack='%s'",
                entry.entity_id, haystack,
            )

    if led_map:
        _LOGGER.info(
            "LED discovery for '%s': %s", config_entry.title, led_map,
        )
    else:
        _LOGGER.warning(
            "LED discovery for '%s': no LED entities mapped "
            "(keypad_type=%s). "
            "If your keypad has LEDs, configure led_entity manually in "
            "the options flow, or check the debug_leds service output.",
            config_entry.title,
            config_entry.data.get("keypad_type"),
        )
    return led_map


# ── LED auto-discovery via button entity naming convention ────────────────────

def _extract_button_number(btn_entry: Any, hass: HomeAssistant) -> int | None:
    """Extract the leap_button_number from a lutron_caseta button entity.

    lutron_caseta unique_id format is typically "<serial>_<leap_button_number>",
    e.g. "20603964_2" → 2.  Several fallback strategies are tried.
    """
    unique_id = btn_entry.unique_id or ""
    entity_id = btn_entry.entity_id or ""

    # Strategy 1: unique_id ends with _<number>  (most common: serial_leapbtn)
    m = _re.search(r"_(\d+)$", unique_id)
    if m:
        return int(m.group(1))

    # Strategy 2: unique_id contains "button_<number>"
    m = _re.search(r"button[_\s](\d+)", unique_id.lower())
    if m:
        return int(m.group(1))

    # Strategy 3: entity state attributes
    state = hass.states.get(entity_id)
    if state:
        for key in ("button_number", "leap_button_number", "button_index"):
            val = state.attributes.get(key)
            if val is not None:
                try:
                    return int(val)
                except (ValueError, TypeError):
                    pass

    # Strategy 4: last number anywhere in unique_id
    nums = _re.findall(r"\d+", unique_id)
    if nums:
        return int(nums[-1])

    return None


def _extract_btn_num_from_led_uid(uid: str, serial: str = "") -> int | None:
    """Extract the leap_button_number from a LED switch entity's unique_id.

    Handles formats:
      <serial>_<num>        e.g. "20603964_2"
      <serial>_<num>_led    e.g. "20603964_2_led"
      <serial>_led_<num>    e.g. "20603964_led_2"
    """
    if not uid:
        return None
    working = uid
    # Strip serial prefix
    if serial and working.startswith(serial + "_"):
        working = working[len(serial) + 1:]
    # Strip _led / led_ markers to isolate the number
    working = _re.sub(r"(?:^led[_-]|[_-]led$)", "", working).strip("_-")
    # Now working should be just the leap_button_number (or close to it)
    m = _re.fullmatch(r"\d+", working)
    if m:
        return int(m.group(0))
    # Last resort: last numeric run
    nums = _re.findall(r"\d+", working)
    if nums:
        return int(nums[-1])
    return None


def _find_lutron_device(hass: HomeAssistant, config_entry: ConfigEntry) -> Any:
    """Locate the HA device-registry entry for our keypad.

    Tries serial match first, then device_name substring match.
    Returns None if not found (with a warning log).
    """
    serial      = str(config_entry.data.get(CONF_DEVICE_SERIAL, "")).strip()
    device_name = config_entry.data.get(CONF_DEVICE_NAME, "").strip().lower()

    dev_reg = dr.async_get(hass)

    # ── Match by Lutron serial (most reliable) ──────────────────────────────
    for device in dev_reg.devices.values():
        for ident_tuple in device.identifiers:
            if (len(ident_tuple) >= 2
                    and ident_tuple[0] == "lutron_caseta"
                    and str(ident_tuple[1]).strip() == serial):
                return device

    # ── Fallback: device name substring match ───────────────────────────────
    if device_name:
        for device in dev_reg.devices.values():
            if (device.name
                    and device_name in device.name.lower()
                    and any(t[0] == "lutron_caseta" for t in device.identifiers)):
                _LOGGER.debug(
                    "LED: serial '%s' not matched; found device '%s' by name",
                    serial, device.name,
                )
                return device

    lutron_devices = [
        (d.name, list(d.identifiers))
        for d in dev_reg.devices.values()
        if any(t[0] == "lutron_caseta" for t in d.identifiers)
    ]
    _LOGGER.warning(
        "LED discovery: no lutron_caseta device matched serial='%s' "
        "device_name='%s'. Available lutron_caseta devices: %s",
        serial, device_name, lutron_devices,
    )
    return None


async def _find_led_entities_by_button_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> dict[int, str]:
    """Find LED switches using multiple strategies against the device registry.

    Strategy A — name-based: button.<base> → switch.<base>_led
    Strategy B — shared unique_id: LED uid == button uid (or button uid + "_led")
    Strategy C — direct uid extraction: parse leap_button_number from LED uid

    The first strategy that yields any results is returned.
    """
    serial  = str(config_entry.data.get(CONF_DEVICE_SERIAL, "")).strip()
    ent_reg = er.async_get(hass)

    lutron_device = _find_lutron_device(hass, config_entry)
    if lutron_device is None:
        return {}

    all_entries = er.async_entries_for_device(ent_reg, lutron_device.id)

    # Collect button and LED switch entities (no platform filter — it can vary by HA version)
    button_entries = [e for e in all_entries if e.domain == "button"]
    led_entries    = [
        e for e in all_entries
        if e.domain == "switch" and e.entity_id.endswith("_led")
    ]

    _LOGGER.debug(
        "LED discovery for '%s': device '%s' has %d button entities, "
        "%d LED switch entities",
        config_entry.title, lutron_device.name,
        len(button_entries), len(led_entries),
    )

    if not led_entries:
        _LOGGER.debug(
            "LED discovery: no switch.*_led entities on device '%s'",
            lutron_device.name,
        )
        return {}

    led_entity_ids = {e.entity_id for e in led_entries}
    led_map: dict[int, str] = {}

    # ── Strategy A: button.xxx → switch.xxx_led ─────────────────────────────
    for btn_e in button_entries:
        base         = btn_e.entity_id[len("button."):]
        expected_led = f"switch.{base}_led"
        if expected_led not in led_entity_ids:
            continue
        btn_num = _extract_button_number(btn_e, hass)
        if btn_num is not None:
            led_map[btn_num] = expected_led
            _LOGGER.debug("LED (A): button %d → '%s'", btn_num, expected_led)

    if led_map:
        _LOGGER.info(
            "LED discovery for '%s' (strategy A): %s",
            config_entry.title, led_map,
        )
        return led_map

    # ── Strategy B: match by shared/related unique_id ───────────────────────
    btn_by_uid: dict[str, Any] = {e.unique_id: e for e in button_entries if e.unique_id}
    for led_e in led_entries:
        if not led_e.unique_id:
            continue
        # Try exact uid match first
        btn_e = btn_by_uid.get(led_e.unique_id)
        if btn_e is None:
            # Try led uid with _led suffix stripped
            base_uid = _re.sub(r"[_-]?led$", "", led_e.unique_id).rstrip("_-")
            btn_e = btn_by_uid.get(base_uid)
        if btn_e:
            btn_num = _extract_button_number(btn_e, hass)
            if btn_num is not None:
                led_map[btn_num] = led_e.entity_id
                _LOGGER.debug("LED (B): button %d → '%s'", btn_num, led_e.entity_id)

    if led_map:
        _LOGGER.info(
            "LED discovery for '%s' (strategy B): %s",
            config_entry.title, led_map,
        )
        return led_map

    # ── Strategy C: extract button number directly from LED entity unique_id ─
    for led_e in led_entries:
        btn_num = _extract_btn_num_from_led_uid(led_e.unique_id or "", serial)
        if btn_num is not None:
            led_map[btn_num] = led_e.entity_id
            _LOGGER.debug("LED (C): button %d → '%s'", btn_num, led_e.entity_id)

    if led_map:
        _LOGGER.info(
            "LED discovery for '%s' (strategy C): %s",
            config_entry.title, led_map,
        )
        return led_map

    _LOGGER.warning(
        "LED discovery for '%s': all strategies failed. "
        "button entities=%s  LED entities=%s  "
        "Configure led_entity manually in options or run debug_leds service.",
        config_entry.title,
        [e.entity_id for e in button_entries],
        [e.entity_id for e in led_entries],
    )
    return led_map


# ── Diagnostic service ────────────────────────────────────────────────────────

async def _async_debug_leds(hass: HomeAssistant, call) -> None:
    """Service: lutron_keypad_controller.debug_leds

    Call from Developer Tools → Actions. Output appears in
    Settings → System → Logs (search "LED DEBUG REPORT").
    Also fires a lutron_keypad_controller_debug event.
    """
    lines: list[str] = []

    entry_controllers: dict = (
        hass.data.get(DOMAIN, {}).get("entry_controllers", {})
    )
    if not entry_controllers:
        lines.append("No entry controllers found in hass.data — "
                     "is the integration loaded?")

    for entry_id, ctrl in entry_controllers.items():
        lines.append(f"\n{'='*60}")
        lines.append(f"Keypad : {ctrl.name}")
        lines.append(f"Serial : {ctrl.serial}")
        lines.append(f"device_id: {ctrl.device_id}")
        lines.append(f"LED map (auto-discovered): {ctrl._led_map}")
        lines.append(
            f"Button switches registered: "
            f"{list(ctrl._button_switches.keys())}"
        )

        for btn_num, btn_cfg in ctrl._buttons.items():
            atype      = btn_cfg.get(CONF_ACTION_TYPE, "none")
            manual_led = btn_cfg.get(CONF_LED_ENTITY, "")
            auto_led   = ctrl._led_map.get(btn_num, "")
            resolved   = manual_led or auto_led
            lines.append(f"\n  Button {btn_num}  action={atype}")
            lines.append(f"    manual led_entity : '{manual_led}'")
            lines.append(f"    auto-discovered   : '{auto_led}'")
            lines.append(f"    resolved LED      : '{resolved}'")
            if resolved:
                state = hass.states.get(resolved)
                lines.append(
                    f"    LED entity state  : "
                    f"{state.state if state else '⚠ ENTITY NOT FOUND'}"
                )
            else:
                lines.append("    ⚠ NO LED ENTITY — "
                             "auto-discovery failed and no manual led_entity set")
            sw = ctrl._button_switches.get(btn_num)
            lines.append(
                f"    HA switch state   : "
                f"{'ON' if sw and sw.is_on else 'OFF'}"
                f"{'' if sw else '  ⚠ switch entity not registered'}"
            )

    lines.append(f"\n{'='*60}")
    lines.append("All switch entities with 'led' in entity_id:")
    for state in hass.states.async_all("switch"):
        if "led" in state.entity_id.lower():
            lines.append(f"  {state.entity_id}: {state.state}")

    lines.append("\nDevice registry — devices with 'lutron' identifiers:")
    dev_reg = dr.async_get(hass)
    for device in dev_reg.devices.values():
        if any("lutron" in str(i).lower() for i in device.identifiers):
            lines.append(f"  '{device.name}'  identifiers={list(device.identifiers)}")

    lines.append("\nEntity registry — lutron_caseta switch entities:")
    ent_reg = er.async_get(hass)
    for entry in ent_reg.entities.values():
        if entry.domain == "switch" and entry.platform == "lutron_caseta":
            lines.append(
                f"  {entry.entity_id}"
                f"  unique_id={entry.unique_id}"
                f"  device_id={entry.device_id}"
            )

    report = "\n".join(lines)
    _LOGGER.warning("LED DEBUG REPORT:\n%s", report)
    hass.bus.async_fire("lutron_keypad_controller_debug", {"report": report})


# ── Setup ─────────────────────────────────────────────────────────────────────

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up via configuration.yaml."""
    hass.data.setdefault(DOMAIN, {})

    if DOMAIN not in config:
        return True

    keypads_cfg: list[dict] = config[DOMAIN].get("keypads", [])
    controllers: list[LutronKeypadsController] = []

    for kp_cfg in keypads_cfg:
        ctrl = LutronKeypadsController(hass, kp_cfg)
        controllers.append(ctrl)
        ctrl.async_register()

    hass.data[DOMAIN]["controllers"] = controllers

    hass.services.async_register(DOMAIN, "debug_leds", _async_debug_leds)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry; reads button config from options (UI) first."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault("controllers", [])
    hass.data[DOMAIN].setdefault("entry_controllers", {})

    buttons_cfg = _build_buttons_from_options(entry.options.get("buttons", {}))

    kp_cfg: dict = {
        "name":           entry.title,
        CONF_DEVICE_SERIAL: entry.data.get(CONF_DEVICE_SERIAL, ""),
        CONF_DEVICE_NAME:   entry.data.get(CONF_DEVICE_NAME, ""),
        CONF_AREA_NAME:     entry.data.get(CONF_AREA_NAME, ""),
        CONF_KEYPAD_TYPE:   entry.data.get(CONF_KEYPAD_TYPE, "generic"),
        "device_id":        entry.data.get("device_id", ""),
        CONF_BUTTONS:       buttons_cfg,
    }

    ctrl = LutronKeypadsController(hass, kp_cfg, config_entry=entry)
    if buttons_cfg:
        ctrl.async_register()
        _LOGGER.info("Keypad '%s' loaded from UI options with %d button(s)", entry.title, len(buttons_cfg))
    else:
        _LOGGER.info(
            "Keypad '%s' loaded (no buttons configured yet). "
            "Click the gear icon to configure buttons, or add YAML under lutron_keypad_controller:",
            entry.title,
        )

    hass.data[DOMAIN]["entry_controllers"][entry.entry_id] = ctrl
    hass.data[DOMAIN]["controllers"].append(ctrl)

    if not hass.services.has_service(DOMAIN, "debug_leds"):
        hass.services.async_register(DOMAIN, "debug_leds", _async_debug_leds)

    # Populate LED map before platforms set up so switch entities can subscribe
    await ctrl.async_initialize()

    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    await _cleanup_orphaned_entities(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _cleanup_orphaned_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove stale entity registry entries from older versions."""
    ent_reg = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        uid = reg_entry.unique_id
        # v2.1.x multi-slot text entities
        if any(f"_entity_{n}" in uid for n in ("2", "3", "4")):
            ent_reg.async_remove(reg_entry.entity_id)
            _LOGGER.info("Removed orphaned multi-slot entity: %s", reg_entry.entity_id)
        # v2.3.x text entities now replaced by read-only sensors
        elif reg_entry.entity_id.startswith("text.") and any(
            uid.endswith(s) for s in ("_entity_1", "_led", "_scene_group")
        ):
            ent_reg.async_remove(reg_entry.entity_id)
            _LOGGER.info("Removed old text entity (now a sensor): %s", reg_entry.entity_id)
        # v3.3.x _enabled switch replaced by _led switch
        elif reg_entry.entity_id.startswith("switch.") and uid.endswith("_enabled"):
            ent_reg.async_remove(reg_entry.entity_id)
            _LOGGER.info("Removed old enabled-toggle switch (now LED switch): %s", reg_entry.entity_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    ctrl = hass.data[DOMAIN].get("entry_controllers", {}).pop(entry.entry_id, None)
    if ctrl is not None:
        ctrl.async_unregister()
        try:
            hass.data[DOMAIN]["controllers"].remove(ctrl)
        except ValueError:
            pass
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options are saved so new button config takes effect."""
    await hass.config_entries.async_reload(entry.entry_id)


# ── LED map key normalization ─────────────────────────────────────────────────

def _normalize_led_map(
    raw_led_map: dict[int, str],
    config_entry: ConfigEntry,
) -> dict[int, str]:
    """Remap LED map keys to match the sequential button numbers used by events and options.

    Events fire with a device-local sequential ``leap_button_number`` (e.g. 1, 2, 3 …).
    LED discovery extracts LEAP *global component IDs* from entity unique_ids
    (e.g. 5376, 5380 …).  These are different number spaces.

    ``get_button_list`` always returns sequential 1-N regardless of bridge
    detection — that is the number space events and the options flow use.
    ``get_button_layout`` uses bridge-detected IDs when available; those IDs
    match the raw_led_map keys when bridge detection succeeded.

    Remapping strategy: sort both sets by value and zip them positionally.
    Lutron assigns global component IDs in physical button order within a device,
    so ascending sort order preserves physical position.
    """
    if not raw_led_map:
        return raw_led_map

    entry_data = config_entry.data
    # Sequential layout is what events use (local leap_button_number 1, 2, 3 …)
    seq_layout = get_button_list(entry_data.get(CONF_KEYPAD_TYPE, KEYPAD_GENERIC))
    seq_numbers = {b["number"] for b in seq_layout}

    # Fast path: keys are already sequential (no remap needed)
    if any(k in seq_numbers for k in raw_led_map):
        return raw_led_map

    # Keys are LEAP global component IDs — remap by ascending sort order
    # (raise/lower buttons don't have LED entities so exclude them as targets)
    configurable_seq = sorted(
        b["number"] for b in seq_layout
        if not b["is_raise"] and not b["is_lower"]
    )
    sorted_leap = sorted(raw_led_map.keys())

    remapped: dict[int, str] = {}
    for btn_num, leap_id in zip(configurable_seq, sorted_leap):
        remapped[btn_num] = raw_led_map[leap_id]

    _LOGGER.info(
        "'%s': LED map: LEAP global IDs %s → sequential button numbers %s",
        config_entry.title,
        sorted_leap,
        list(remapped.keys()),
    )
    return remapped


# ── Controller ────────────────────────────────────────────────────────────────

class LutronKeypadsController:
    """Manages a single Lutron keypad and dispatches button events."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        self.hass = hass
        self.name: str = config["name"]
        self.serial: str = str(config.get(CONF_DEVICE_SERIAL, "")).strip()
        self.device_id: str = str(config.get("device_id", "")).strip()
        self.device_name: str = config.get(CONF_DEVICE_NAME, "").strip().lower()
        self.area_name: str = config.get(CONF_AREA_NAME, "").strip().lower()
        self.keypad_type: str = config.get(CONF_KEYPAD_TYPE, "generic")
        self.scene_group: str = config.get("scene_group", "").strip()
        self._config_entry = config_entry

        # Index buttons by button_number
        self._buttons: dict[int, dict] = {}
        for btn in config.get(CONF_BUTTONS, []):
            self._buttons[btn[CONF_BUTTON_NUMBER]] = btn

        # Per-controller runtime state
        self._active_scene_btn: int | None = None
        self._last_action: dict | None = None
        self._cover_states: dict[int, str] = {}
        self._light_dim_indices: dict[int, int] = {}
        self._unsubscribe = None

        # LED / switch entity tracking
        self._led_map: dict[int, str] = {}       # btn_num → auto-discovered led entity_id
        self._button_switches: dict[int, Any] = {}  # btn_num → LutronButtonSwitch
        # LEAP button number → configured button number
        # Events use leap_button_number; config stores button_number (can differ for raise/lower)
        self._leap_btn_map: dict[int, int] = {}

        # Press-and-hold tracking (synchronous call_later state machine)
        self._press_times:     dict[int, float] = {}  # monotonic time of last press
        self._release_counts:  dict[int, int]   = {}  # releases seen since last press
        self._held:            dict[int, bool]  = {}  # True while hold-event ramp is active
        self._confirm_handles: dict             = {}  # call_later handle: hold-confirm window
        self._ramp_tasks:  dict[int, asyncio.Task] = {}  # active ramp coroutine per button
        self._ramp_dirs:       dict[int, str]   = {}  # last ramp direction per button
        self._ramp_end_times:  dict[int, float] = {}  # time last ramp ended per button

        # Sensors to notify when _last_action changes
        self._state_sensors: list = []

        # Entity-state tracking for entity_toggle LED sync (Room/Scene Mode)
        self._entity_tracking_unsubs: list = []

    # ── Registration ──────────────────────────────────────────────────────────

    @callback
    def async_register(self) -> None:
        """Subscribe to lutron_caseta_button_event events."""
        self._unsubscribe = self.hass.bus.async_listen(LUTRON_EVENT, self._handle_event)
        _LOGGER.info("Lutron Keypad Controller '%s' registered (serial=%s)", self.name, self.serial)

    @callback
    def async_unregister(self) -> None:
        for unsub in self._entity_tracking_unsubs:
            unsub()
        self._entity_tracking_unsubs.clear()
        """Unsubscribe from events (called on entry unload)."""
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
            _LOGGER.debug("Lutron Keypad Controller '%s' unregistered", self.name)
        for handle in self._confirm_handles.values():
            handle.cancel()
        self._confirm_handles.clear()
        for task in self._ramp_tasks.values():
            task.cancel()
        self._ramp_tasks.clear()
        self._press_times.clear()
        self._release_counts.clear()
        self._held.clear()
        self._ramp_end_times.clear()

    # ── Initialization ────────────────────────────────────────────────────────

    def _get_lutron_bridge(self):
        """Return the pylutron-caseta bridge object, trying all known storage locations."""
        from homeassistant.config_entries import ConfigEntryState
        for entry in self.hass.config_entries.async_entries("lutron_caseta"):
            if entry.state is not ConfigEntryState.LOADED:
                continue
            runtime = getattr(entry, "runtime_data", None)
            if runtime is not None:
                bridge = getattr(runtime, "bridge", None)
                if bridge is not None:
                    return bridge
            entry_data = self.hass.data.get("lutron_caseta", {}).get(entry.entry_id)
            if entry_data is not None:
                bridge = getattr(entry_data, "bridge", None)
                if bridge is None and isinstance(entry_data, dict):
                    bridge = entry_data.get("bridge")
                if bridge is not None:
                    return bridge
        return None

    async def _build_leap_btn_map(self) -> None:
        """Map LEAP button numbers (used in events) to configured button numbers.

        button_devices stores the canonical button_number (e.g. 7 for raise).
        LEAP events fire with leap_button_number (e.g. 18).  Without this map
        the event handler looks up btn_num=18, finds nothing, and ignores the press.
        """
        bridge = self._get_lutron_bridge()
        if bridge is None:
            _LOGGER.debug("'%s': _build_leap_btn_map — lutron_caseta bridge not found", self.name)
            return

        button_devices: dict = getattr(bridge, "button_devices", None) or {}
        if not button_devices:
            _LOGGER.debug(
                "'%s': _build_leap_btn_map — bridge has no button_devices "
                "(expected for Caseta Pro; raise/lower remapping not available)",
                self.name,
            )
            return

        matched = 0
        for bd in button_devices.values():
            bd_serial    = str(bd.get("serial", ""))
            bd_device_id = str(bd.get("device_id", ""))
            if bd_serial != self.serial and bd_device_id != self.device_id:
                continue
            matched += 1
            # Canonical number — same priority as _detect_button_layout
            canonical = None
            for key in ("button_number", "leap_button_number"):
                raw = bd.get(key)
                if raw is not None:
                    try:
                        canonical = int(raw)
                        break
                    except (TypeError, ValueError):
                        pass
            leap_raw = bd.get("leap_button_number")
            if canonical is not None and leap_raw is not None:
                try:
                    self._leap_btn_map[int(leap_raw)] = canonical
                except (TypeError, ValueError):
                    pass

        _LOGGER.debug(
            "'%s': _build_leap_btn_map — matched %d button_devices entries, map=%s",
            self.name, matched, self._leap_btn_map,
        )

    async def async_initialize(self) -> None:
        """Discover LED entities — button-entity method first, registry scan as fallback."""
        if self._config_entry is None:
            return
        await self._build_leap_btn_map()
        raw_map = await _find_led_entities_by_button_entities(
            self.hass, self._config_entry
        )
        if not raw_map:
            _LOGGER.debug(
                "'%s': button-entity LED discovery found nothing — trying registry scan",
                self.name,
            )
            raw_map = await _find_led_entities(self.hass, self._config_entry)
        if raw_map:
            self._led_map = _normalize_led_map(raw_map, self._config_entry)
            _LOGGER.warning(
                "'%s': LED map ready (keys = sequential button numbers): %s",
                self.name, self._led_map,
            )
        else:
            _LOGGER.debug(
                "'%s': no LED entities found (expected for CASETA Pro keypads "
                "without LED feedback). Call debug_leds service to diagnose.",
                self.name,
            )

        self._setup_entity_state_tracking()

    # ── LED helpers ───────────────────────────────────────────────────────────

    def _get_led_entity(self, btn_num: int) -> str | None:
        """Return LED entity for a button; manual config takes priority over auto-discovery."""
        manual = self._buttons.get(btn_num, {}).get(CONF_LED_ENTITY, "")
        return manual if manual else self._led_map.get(btn_num)

    def register_button_switch(self, btn_num: int, switch: Any) -> None:
        self._button_switches[btn_num] = switch
        # Sync initial LED state now that the switch entity is registered.
        # For entity_toggle buttons the LED tracks entity states (Room/Scene Mode),
        # not the last button press, so we push the correct value immediately.
        btn_cfg = self._buttons.get(btn_num, {})
        if btn_cfg.get(CONF_ACTION_TYPE) == ACTION_ENTITY_TOGGLE:
            entities = _normalize_targets(btn_cfg.get(CONF_ACTION_TARGET, []))
            if entities:
                self._update_entity_toggle_led(btn_num, btn_cfg, entities)

    @callback
    def _update_entity_toggle_led(
        self, btn_num: int, btn_cfg: dict, entities: list[str]
    ) -> None:
        """Update LED for entity_toggle button using the configured LED mode."""
        mode = btn_cfg.get(CONF_LED_MODE, LED_MODE_ROOM)
        if mode == LED_MODE_SCENE:
            self._update_scene_mode_led(btn_num, entities)
        else:
            self._update_room_mode_led(btn_num, entities)

    @callback
    def _update_room_mode_led(self, btn_num: int, entities: list[str]) -> None:
        """Room Mode: LED on if ANY assigned entity is on, off when all are off."""
        any_on = any(
            (st := self.hass.states.get(eid)) is not None
            and st.state not in ("off", "closed", "unavailable", "unknown", "none")
            for eid in entities
        )
        self._update_button_switch_state(btn_num, any_on)

    @callback
    def _update_scene_mode_led(self, btn_num: int, entities: list[str]) -> None:
        """Scene Mode: LED on only when ALL assigned entities are on, off otherwise."""
        all_on = bool(entities) and all(
            (st := self.hass.states.get(eid)) is not None
            and st.state not in ("off", "closed", "unavailable", "unknown", "none")
            for eid in entities
        )
        self._update_button_switch_state(btn_num, all_on)

    def _setup_entity_state_tracking(self) -> None:
        """Subscribe to state changes for entity_toggle buttons (Room/Scene Mode LED sync)."""
        for unsub in self._entity_tracking_unsubs:
            unsub()
        self._entity_tracking_unsubs.clear()

        for btn_num, btn_cfg in self._buttons.items():
            if btn_cfg.get(CONF_ACTION_TYPE) != ACTION_ENTITY_TOGGLE:
                continue
            entities = _normalize_targets(btn_cfg.get(CONF_ACTION_TARGET, []))
            if not entities:
                continue

            mode = btn_cfg.get(CONF_LED_MODE, LED_MODE_ROOM)

            @callback
            def _on_entity_change(
                event: Any, _btn=btn_num, _cfg=btn_cfg, _ents=entities
            ) -> None:
                self._update_entity_toggle_led(_btn, _cfg, _ents)

            unsub = async_track_state_change_event(self.hass, entities, _on_entity_change)
            self._entity_tracking_unsubs.append(unsub)
            _LOGGER.debug(
                "'%s': button %d: %s LED tracking %s",
                self.name, btn_num, mode, entities,
            )

    def register_state_sensor(self, sensor: Any) -> None:
        if sensor not in self._state_sensors:
            self._state_sensors.append(sensor)

    @callback
    def _notify_state_sensors(self) -> None:
        for sensor in self._state_sensors:
            sensor.async_write_ha_state()

    def _update_button_switch_state(self, btn_num: int, is_on: bool) -> None:
        switch = self._button_switches.get(btn_num)
        if switch is not None:
            switch.update_led_state(is_on)

    async def _write_led_entity(self, btn_num: int, is_on: bool) -> None:
        """Write ON/OFF to the physical LED switch entity bound to this button.

        Respects the per-button ``led_invert`` flag — when True the logical
        on/off is flipped before writing (useful for "lights off" indicators).

        This both lights up the physical Lutron keypad LED and triggers
        _handle_led_state_change in switch.py which mirrors the state to our
        HA button switch.  No-op when no LED entity is bound.
        """
        led_entity = self._get_led_entity(btn_num)
        if not led_entity:
            return
        btn_cfg = self._buttons.get(btn_num, {})
        if btn_cfg.get(CONF_LED_INVERT, False):
            is_on = not is_on
        service = SERVICE_TURN_ON if is_on else SERVICE_TURN_OFF
        try:
            await self.hass.services.async_call(
                "switch", service, {ATTR_ENTITY_ID: led_entity}, blocking=True
            )
            _LOGGER.debug(
                "'%s': button %d LED '%s' → %s",
                self.name, btn_num, led_entity, "ON" if is_on else "OFF",
            )
        except Exception as exc:
            _LOGGER.warning(
                "'%s': button %d could not write LED entity '%s': %s",
                self.name, btn_num, led_entity, exc,
            )

    async def _write_group_leds(self, active_btn: int, active_btn_cfg: dict) -> None:
        """For stateful_scene buttons: turn ON active button's LED, OFF all others in group."""
        group = active_btn_cfg.get("scene_group") or self.scene_group
        for btn_num, btn_cfg in self._buttons.items():
            if btn_cfg.get(CONF_ACTION_TYPE) != ACTION_STATEFUL_SCENE:
                continue
            if not self._get_led_entity(btn_num):
                continue  # no LED entity bound; _sync_leds handles HA switch state
            btn_group = btn_cfg.get("scene_group") or self.scene_group
            if group and btn_group != group:
                continue
            await self._write_led_entity(btn_num, btn_num == active_btn)

    async def _sync_leds(self, active_btn: int | None) -> None:
        """Update HA switch states for stateful_scene buttons that have no LED entity.

        Buttons that have a physical LED entity binding are skipped — their state
        is driven by _handle_led_state_change after _write_group_leds writes to
        the physical LED.
        """
        _LOGGER.debug("'%s': _sync_leds called, active_btn=%s", self.name, active_btn)
        for btn_num, btn_cfg in self._buttons.items():
            if btn_cfg.get(CONF_ACTION_TYPE) != ACTION_STATEFUL_SCENE:
                continue
            if self._get_led_entity(btn_num):
                continue
            should_be_on = (btn_num == active_btn)
            _LOGGER.debug(
                "'%s': Button %d (no LED entity) should_be_on=%s",
                self.name, btn_num, should_be_on,
            )
            self._update_button_switch_state(btn_num, should_be_on)

    # ── Event matching ────────────────────────────────────────────────────────

    def _matches_event(self, event_data: dict) -> bool:
        """Return True if this event belongs to our keypad."""
        # device_id is the most reliable — immune to serial type mismatches
        ev_device_id = str(event_data.get("device_id", "")).strip()
        if ev_device_id and self.device_id and ev_device_id == self.device_id:
            return True

        # Serial — convert both sides to string; Lutron fires it as an int
        if self.serial:
            ev_serial = str(event_data.get("serial", "")).strip()
            if ev_serial and ev_serial == str(self.serial):
                return True

        # Last resort: device_name + area_name
        ev_device = str(event_data.get("device_name", "")).lower()
        ev_area   = str(event_data.get("area_name", "")).lower()

        if self.device_name and self.area_name:
            return ev_device == self.device_name and ev_area == self.area_name
        if self.device_name:
            return ev_device == self.device_name
        if self.area_name:
            return ev_area == self.area_name

        return False

    # ── Main event handler ────────────────────────────────────────────────────

    @callback
    def _handle_event(self, event: Event) -> None:
        """Called for every lutron_caseta_button_event on the bus."""
        data = event.data

        _LOGGER.debug(
            "'%s': event received — serial=%s device_id=%s "
            "btn=%s leap_btn=%s action=%s",
            self.name,
            data.get("serial"), data.get("device_id"),
            data.get("button_number"), data.get("leap_button_number"),
            data.get("action"),
        )

        if not self._matches_event(data):
            _LOGGER.debug(
                "'%s': ignoring event — ev serial=%s device_id=%s / "
                "our serial=%s device_id=%s",
                self.name,
                data.get("serial"), data.get("device_id"),
                self.serial, self.device_id,
            )
            return

        # Resolve button number: prefer button_number, fall back to leap_button_number.
        # Then translate through _leap_btn_map so that raise/lower buttons whose
        # button_devices entry uses button_number=7/8 but events fire leap_button_number=18/19
        # are correctly mapped to the configured key.
        raw_btn = data.get("button_number")
        if raw_btn is None:
            raw_leap = data.get("leap_button_number")
            if raw_leap is None:
                _LOGGER.debug(
                    "'%s': event has no button_number or leap_button_number: %s",
                    self.name, data,
                )
                return
            leap_int = int(raw_leap)
            raw_btn = self._leap_btn_map.get(leap_int, leap_int)
        btn_num = int(raw_btn)

        _LOGGER.debug(
            "'%s': matched — resolved btn_num=%d, configured buttons=%s",
            self.name, btn_num, list(self._buttons.keys()),
        )

        btn_cfg = self._buttons.get(btn_num)
        if btn_cfg is None:
            _LOGGER.debug(
                "'%s': button %d pressed but not configured — ignoring", self.name, btn_num
            )
            return

        action_event = data.get("action", "press")

        if action_event == "release":
            self._handle_release(btn_num)
            return

        _LOGGER.info(
            "'%s': button %d (%s) pressed — action_type=%s",
            self.name,
            btn_num,
            btn_cfg.get(CONF_BUTTON_LABEL, ""),
            btn_cfg[CONF_ACTION_TYPE],
        )

        self._on_press(btn_num, btn_cfg)

    # ── Press / release / hold event ─────────────────────────────────────────
    #
    # Hardware reality: some Lutron bridges send an automatic "fake" release
    # (~10–25 ms) on every press while the finger is still down; others send
    # only ONE release when the finger actually lifts.  We handle both:
    #
    #   PRESS    → arm hold timer (_HOLD_CONFIRM ms from press).
    #              Non-hold actions dispatch immediately.
    #
    #   RELEASE  → elapsed < _FAKE_WINDOW (25 ms): Lutron fake — ignore.
    #            → _held (ramp running): stop ramp.
    #            → else (real lift before timer): cancel timer → TAP → dispatch.
    #
    #   _on_hold_event fires (_HOLD_CONFIRM ms after press, no release yet):
    #              HOLD: start ramp (or dispatch if LED is off / no rampable lights).
    #              Next hold within 2 s alternates ramp direction.
    #
    # _HOLD_CONFIRM must exceed the user's natural quick-tap duration.
    # Observed tap release times on this hardware: ~440 ms → 600 ms gives margin.

    _FAKE_WINDOW   = 0.025  # seconds — releases within this window are Lutron fakes
    _HOLD_CONFIRM  = 0.60   # seconds after PRESS before hold event fires
    _RAMP_STEP_PCT = 10     # brightness % per ramp tick
    _RAMP_INTERVAL = 0.40   # seconds between ticks (also used as transition time)

    _HOLD_ACTIONS = frozenset({
        ACTION_ENTITY_TOGGLE, ACTION_STATEFUL_SCENE, ACTION_RAISE, ACTION_LOWER
    })

    @callback
    def _on_press(self, btn_num: int, btn_cfg: dict) -> None:
        """Synchronous press handler."""
        old_confirm = self._confirm_handles.pop(btn_num, None)
        if old_confirm is not None:
            old_confirm.cancel()
        old_ramp = self._ramp_tasks.pop(btn_num, None)
        if old_ramp is not None and not old_ramp.done():
            old_ramp.cancel()

        self._press_times[btn_num]    = asyncio.get_event_loop().time()
        self._release_counts[btn_num] = 0
        self._held[btn_num]           = False

        action = btn_cfg.get(CONF_ACTION_TYPE)
        if action not in self._HOLD_ACTIONS:
            self.hass.async_create_task(self._dispatch(btn_num, btn_cfg))
        else:
            # Arm hold timer starting from press — fires if finger is still down
            handle = self.hass.loop.call_later(
                self._HOLD_CONFIRM, self._on_hold_event, btn_num,
            )
            self._confirm_handles[btn_num] = handle

    @callback
    def _handle_release(self, btn_num: int) -> None:
        """Synchronous release handler — drives the press/hold state machine."""
        now     = asyncio.get_event_loop().time()
        elapsed = now - self._press_times.get(btn_num, now)
        count   = self._release_counts.get(btn_num, 0) + 1
        self._release_counts[btn_num] = count

        _LOGGER.debug(
            "'%s': button %d release #%d elapsed=%.3fs held=%s confirm=%s",
            self.name, btn_num, count, elapsed,
            self._held.get(btn_num), btn_num in self._confirm_handles,
        )

        # ── Lutron hardware fake (~10–25 ms) — ignore ────────────────────────
        if elapsed < self._FAKE_WINDOW:
            return

        # ── Ramp is active: this release stops it ────────────────────────────
        if self._held.get(btn_num, False):
            ramp = self._ramp_tasks.pop(btn_num, None)
            if ramp is not None and not ramp.done():
                ramp.cancel()
            self._held.pop(btn_num, None)
            self._ramp_end_times[btn_num] = now
            return

        # ── Real lift before hold timer fires → TAP ──────────────────────────
        confirm = self._confirm_handles.pop(btn_num, None)
        if confirm is not None:
            confirm.cancel()
        btn_cfg = self._buttons.get(btn_num)
        if btn_cfg is not None and btn_cfg.get(CONF_ACTION_TYPE) in self._HOLD_ACTIONS:
            self.hass.async_create_task(self._dispatch(btn_num, btn_cfg))

    @callback
    def _on_hold_event(self, btn_num: int) -> None:
        """Internal hold event — fires _HOLD_CONFIRM seconds after the fake release
        with no real release in between.  Routes to ramp or dispatch based on context.
        """
        self._confirm_handles.pop(btn_num, None)

        btn_cfg = self._buttons.get(btn_num)
        if btn_cfg is None:
            return

        action = btn_cfg.get(CONF_ACTION_TYPE)

        if action == ACTION_RAISE:
            direction = "up"
            entities  = self._get_last_ramp_lights()
        elif action == ACTION_LOWER:
            direction = "down"
            entities  = self._get_last_ramp_lights()
        else:
            # entity_toggle / stateful_scene: only ramp when LED is currently ON
            if not self._is_btn_led_on(btn_num):
                _LOGGER.debug(
                    "'%s': button %d hold event — LED off, dispatching instead",
                    self.name, btn_num,
                )
                # Mark held so the eventual real-release won't dispatch a second time.
                self._held[btn_num] = True
                self.hass.async_create_task(self._dispatch(btn_num, btn_cfg))
                return
            entities  = self._get_btn_light_entities(btn_cfg)
            direction = self._next_ramp_dir(btn_num, entities)

        if not entities:
            _LOGGER.debug(
                "'%s': button %d hold event — no rampable lights, dispatching",
                self.name, btn_num,
            )
            self._held[btn_num] = True
            self.hass.async_create_task(self._dispatch(btn_num, btn_cfg))
            return

        _LOGGER.info(
            "'%s': button %d HOLD EVENT — ramp %s on %s",
            self.name, btn_num, direction, entities,
        )
        self._held[btn_num] = True
        task = self.hass.async_create_task(
            self._ramp_loop(btn_num, entities, direction)
        )
        self._ramp_tasks[btn_num] = task

    async def _ramp_loop(
        self,
        btn_num: int,
        entities: list[str],
        direction: str,
    ) -> None:
        """Step brightness up/down until cancelled by _handle_release."""
        try:
            while True:
                all_at_limit = True
                for eid in entities:
                    state = self.hass.states.get(eid)
                    if state is None:
                        continue
                    if state.state == "off":
                        if direction == "up":
                            await self.hass.services.async_call(
                                "light", SERVICE_TURN_ON,
                                {ATTR_ENTITY_ID: eid, "brightness_pct": 1},
                                blocking=False,
                            )
                            all_at_limit = False
                        continue
                    current_pct = round(
                        (state.attributes.get("brightness", 0) or 0) / 255 * 100
                    )
                    new_pct = (
                        min(100, current_pct + self._RAMP_STEP_PCT)
                        if direction == "up"
                        else max(0, current_pct - self._RAMP_STEP_PCT)
                    )
                    if new_pct == current_pct:
                        continue
                    all_at_limit = False
                    if direction == "down" and new_pct <= 0:
                        await self.hass.services.async_call(
                            "light", SERVICE_TURN_OFF,
                            {ATTR_ENTITY_ID: eid}, blocking=False,
                        )
                    else:
                        await self.hass.services.async_call(
                            "light", SERVICE_TURN_ON,
                            {
                                ATTR_ENTITY_ID: eid,
                                "brightness_pct": new_pct,
                                "transition": self._RAMP_INTERVAL,
                            },
                            blocking=False,
                        )
                if all_at_limit:
                    break
                await asyncio.sleep(self._RAMP_INTERVAL)
        except asyncio.CancelledError:
            pass
        finally:
            self._ramp_tasks.pop(btn_num, None)

    # ── Ramp helpers ──────────────────────────────────────────────────────────

    _RAMP_DIR_RESET_WINDOW = 5.0  # seconds — gap longer than this resets direction

    def _next_ramp_dir(self, btn_num: int, entities: list[str] | None = None) -> str:
        """Return next ramp direction, cycling on repeated holds within the reset window.

        Fresh start (first hold, or gap > 5 s): default "up", unless every
        rampable light is already at 100% — in that case default "down".
        """
        now = asyncio.get_event_loop().time()
        last_end = self._ramp_end_times.get(btn_num)
        if last_end is None or (now - last_end) > self._RAMP_DIR_RESET_WINDOW:
            if entities and all(self._light_at_max(e) for e in entities):
                direction = "down"
            else:
                direction = "up"
        else:
            last_dir = self._ramp_dirs.get(btn_num, "down")
            direction = "up" if last_dir == "down" else "down"
        self._ramp_dirs[btn_num] = direction
        return direction

    def _light_at_max(self, eid: str) -> bool:
        state = self.hass.states.get(eid)
        if state is None or state.state != "on":
            return False
        return round((state.attributes.get("brightness", 0) or 0) / 255 * 100) >= 99

    def _is_btn_led_on(self, btn_num: int) -> bool:
        sw = self._button_switches.get(btn_num)
        if sw is not None:
            return bool(sw.is_on)
        led = self._get_led_entity(btn_num)
        if led:
            st = self.hass.states.get(led)
            return st is not None and st.state == "on"
        return False

    def _get_btn_light_entities(self, btn_cfg: dict) -> list[str]:
        """Return light entity_ids rampable for this button's action."""
        action = btn_cfg.get(CONF_ACTION_TYPE)
        if action == ACTION_ENTITY_TOGGLE:
            return [
                e for e in _normalize_targets(btn_cfg.get(CONF_ACTION_TARGET, []))
                if e.startswith("light.")
            ]
        if action == ACTION_STATEFUL_SCENE:
            scene_id = btn_cfg.get(CONF_ACTION_TARGET, "")
            st = self.hass.states.get(scene_id) if scene_id else None
            if st:
                return [
                    e for e in st.attributes.get("entity_id", [])
                    if e.startswith("light.")
                ]
        return []

    def _scene_light_entities(self, scene_id: str) -> list[str]:
        """Return light entity_ids that belong to an HA scene."""
        state = self.hass.states.get(scene_id)
        if state is None:
            return []
        return [e for e in state.attributes.get("entity_id", []) if e.startswith("light.")]

    def _get_last_ramp_lights(self) -> list[str]:
        """Return light entities from the most recent action (for raise/lower ramp)."""
        if self._last_action is None:
            return []
        entities = self._last_action.get("entities", [])
        if entities:
            return [e for e in entities if e.startswith("light.")]
        # Fallback for scene-type actions that didn't store entities directly
        action_type = self._last_action.get("type")
        if action_type in (ACTION_STATEFUL_SCENE, ACTION_HA_SCENE):
            scene_id = self._last_action.get("scene_id", "")
            return self._scene_light_entities(scene_id) if scene_id else []
        return []

    # ── Dispatch ──────────────────────────────────────────────────────────────

    async def _dispatch(self, btn_num: int, btn_cfg: dict) -> None:
        action = btn_cfg[CONF_ACTION_TYPE]
        target = btn_cfg.get(CONF_ACTION_TARGET)
        params = btn_cfg.get(CONF_ACTION_PARAMS, {})

        if action == ACTION_NONE:
            return

        elif action == ACTION_HA_SCENE:
            await self._activate_scene(target)
            await self._write_led_entity(btn_num, True)
            self._last_action = {"type": ACTION_HA_SCENE, "scene_id": target}

        elif action == ACTION_STATEFUL_SCENE:
            # LED writes handled inside _activate_stateful_scene
            await self._activate_stateful_scene(btn_num, btn_cfg, target)

        elif action == ACTION_AUTOMATION:
            await self._trigger_automation(target)
            await self._write_led_entity(btn_num, True)

        elif action == ACTION_SCRIPT:
            await self._run_script(target, params)
            await self._write_led_entity(btn_num, True)

        elif action == ACTION_ENTITY_TOGGLE:
            # Read state BEFORE toggling — HA state propagation is async even
            # with blocking=True, so reading after the call returns the old value.
            # Inverting the pre-toggle state gives the correct post-toggle state.
            entity_ids = _normalize_targets(target)
            pre_on = False
            if entity_ids:
                pre_state = self.hass.states.get(entity_ids[0])
                pre_on = pre_state is not None and pre_state.state not in (
                    "off", "closed", "unavailable", "unknown", "none"
                )
            await self._entity_toggle(target)
            await self._write_led_entity(btn_num, not pre_on)

        elif action == ACTION_COVER_CYCLE:
            await self._cover_cycle(btn_num, target)

        elif action == ACTION_LIGHT_CYCLE_DIM:
            levels = params.get("levels", DIM_CYCLE_LEVELS)
            await self._light_cycle_dim(btn_num, target, levels)

        elif action == ACTION_RAISE:
            await self._raise(params)

        elif action == ACTION_LOWER:
            await self._lower(params)

        else:
            _LOGGER.error("'%s': unknown action_type '%s'", self.name, action)
            return

        if self._last_action is not None:
            self._last_action.setdefault("button", btn_num)
        self._notify_state_sensors()

    # ── Action implementations ────────────────────────────────────────────────

    async def _activate_scene(self, scene_id: str) -> None:
        """Activate a plain HA scene."""
        await self.hass.services.async_call(
            "scene", "turn_on", {ATTR_ENTITY_ID: scene_id}, blocking=True
        )
        _LOGGER.debug("Scene activated: %s", scene_id)

    async def _activate_stateful_scene(
        self, btn_num: int, btn_cfg: dict, scene_id: str
    ) -> None:
        """Activate an HA scene and update stateful tracking + LEDs."""
        await self._activate_scene(scene_id)

        self._active_scene_btn = btn_num

        group = btn_cfg.get("scene_group") or self.scene_group
        if group:
            _SCENE_GROUPS[group] = btn_num

        # Buttons without LED entity binding: update HA switch state directly
        await self._sync_leds(btn_num)
        # Buttons with LED entity binding: write to physical LED (triggers _handle_led_state_change)
        await self._write_group_leds(btn_num, btn_cfg)

        self._last_action = {
            "type": ACTION_STATEFUL_SCENE,
            "scene_id": scene_id,
            "button": btn_num,
        }
        _LOGGER.debug("Stateful scene '%s' activated on btn %d", scene_id, btn_num)

    async def _trigger_automation(self, automation_id: str) -> None:
        """Trigger an HA automation."""
        await self.hass.services.async_call(
            "automation",
            "trigger",
            {ATTR_ENTITY_ID: automation_id, "skip_condition": True},
            blocking=True,
        )
        self._last_action = {"type": ACTION_AUTOMATION, "id": automation_id}

    async def _run_script(self, script_id: str, params: dict) -> None:
        """Run an HA script with optional variables."""
        service_data: dict[str, Any] = {ATTR_ENTITY_ID: script_id}
        if "variables" in params:
            service_data["variables"] = params["variables"]
        await self.hass.services.async_call(
            "script", "turn_on", service_data, blocking=False
        )
        self._last_action = {"type": ACTION_SCRIPT, "id": script_id}

    async def _entity_toggle(self, targets: Any) -> None:
        """Toggle one or more entities."""
        entity_ids = _normalize_targets(targets)
        for eid in entity_ids:
            domain = eid.split(".")[0]
            await self.hass.services.async_call(
                domain, SERVICE_TOGGLE, {ATTR_ENTITY_ID: eid}, blocking=True
            )
        self._last_action = {"type": ACTION_ENTITY_TOGGLE, "entities": entity_ids}

    async def _cover_cycle(self, btn_num: int, targets: Any) -> None:
        """Cycle a cover: open → stop → close → open ..."""
        entity_ids = _normalize_targets(targets)
        current = self._cover_states.get(btn_num, COVER_STATE_CLOSE)

        if current == COVER_STATE_CLOSE:
            next_state = COVER_STATE_OPEN
            service = "open_cover"
        elif current == COVER_STATE_OPEN:
            next_state = COVER_STATE_STOP
            service = "stop_cover"
        else:  # STOP
            next_state = COVER_STATE_CLOSE
            service = "close_cover"

        self._cover_states[btn_num] = next_state
        await self.hass.services.async_call(
            "cover", service, {ATTR_ENTITY_ID: entity_ids}, blocking=True
        )
        self._last_action = {
            "type": ACTION_COVER_CYCLE,
            "entities": entity_ids,
            "state": next_state,
        }
        _LOGGER.debug("Cover cycle: %s → %s on %s", current, next_state, entity_ids)

    async def _light_cycle_dim(
        self, btn_num: int, targets: Any, levels: list[int]
    ) -> None:
        """Cycle a light through dim levels, then off."""
        entity_ids = _normalize_targets(targets)
        idx = self._light_dim_indices.get(btn_num, len(levels))  # start past end = off state

        if idx >= len(levels):
            # Currently off (or past last level) → turn on at first level
            idx = 0
        else:
            idx += 1

        if idx >= len(levels):
            # Past the last level → turn off
            await self.hass.services.async_call(
                "light", SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_ids}, blocking=True
            )
            self._light_dim_indices[btn_num] = len(levels)  # mark as off
            self._last_action = {
                "type": ACTION_LIGHT_CYCLE_DIM,
                "entities": entity_ids,
                "brightness": 0,
            }
            _LOGGER.debug("Light cycle: turned off %s", entity_ids)
        else:
            brightness_pct = levels[idx]
            brightness_255 = int(brightness_pct / 100 * 255)
            await self.hass.services.async_call(
                "light",
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: entity_ids, "brightness": brightness_255},
                blocking=True,
            )
            self._light_dim_indices[btn_num] = idx
            self._last_action = {
                "type": ACTION_LIGHT_CYCLE_DIM,
                "entities": entity_ids,
                "brightness": brightness_pct,
            }
            _LOGGER.debug("Light cycle: %s → %d%%", entity_ids, brightness_pct)

    def _last_action_light_entities(self) -> list[str]:
        """Resolve light entities from the last action regardless of action type."""
        if self._last_action is None:
            return []
        entities = self._last_action.get("entities", [])
        if entities:
            return [e for e in entities if e.startswith("light.")]
        action_type = self._last_action.get("type")
        if action_type in (ACTION_STATEFUL_SCENE, ACTION_HA_SCENE):
            scene_id = self._last_action.get("scene_id", "")
            return self._scene_light_entities(scene_id) if scene_id else []
        return []

    async def _raise(self, params: dict) -> None:
        """Raise shades or brighten lights based on last action context."""
        if self._last_action is None:
            _LOGGER.debug("'%s': RAISE pressed but no prior context", self.name)
            return

        last = self._last_action
        action_type = last.get("type")
        entities = last.get("entities", [])

        if action_type == ACTION_COVER_CYCLE or _entities_are_covers(entities):
            await self.hass.services.async_call(
                "cover", "open_cover", {ATTR_ENTITY_ID: entities}, blocking=True
            )
            for btn, cfg in self._buttons.items():
                if cfg.get(CONF_ACTION_TYPE) == ACTION_COVER_CYCLE and cfg.get(CONF_ACTION_TARGET):
                    tgts = _normalize_targets(cfg[CONF_ACTION_TARGET])
                    if any(t in entities for t in tgts):
                        self._cover_states[btn] = COVER_STATE_OPEN
        else:
            lights = self._last_action_light_entities()
            if lights:
                await self._adjust_light_brightness(lights, +RAISE_LOWER_STEP)
            else:
                _LOGGER.debug("'%s': RAISE — no applicable entities from last action", self.name)

    async def _lower(self, params: dict) -> None:
        """Lower shades or dim lights based on last action context."""
        if self._last_action is None:
            _LOGGER.debug("'%s': LOWER pressed but no prior context", self.name)
            return

        last = self._last_action
        action_type = last.get("type")
        entities = last.get("entities", [])

        if action_type == ACTION_COVER_CYCLE or _entities_are_covers(entities):
            await self.hass.services.async_call(
                "cover", "close_cover", {ATTR_ENTITY_ID: entities}, blocking=True
            )
            for btn, cfg in self._buttons.items():
                if cfg.get(CONF_ACTION_TYPE) == ACTION_COVER_CYCLE and cfg.get(CONF_ACTION_TARGET):
                    tgts = _normalize_targets(cfg[CONF_ACTION_TARGET])
                    if any(t in entities for t in tgts):
                        self._cover_states[btn] = COVER_STATE_CLOSE
        else:
            lights = self._last_action_light_entities()
            if lights:
                await self._adjust_light_brightness(lights, -RAISE_LOWER_STEP)
            else:
                _LOGGER.debug("'%s': LOWER — no applicable entities from last action", self.name)

    async def _adjust_light_brightness(
        self, entities: list[str], delta_pct: int
    ) -> None:
        """Adjust brightness of lights by delta_pct (positive = brighter)."""
        for eid in entities:
            state = self.hass.states.get(eid)
            if state is None:
                continue
            domain = eid.split(".")[0]
            if domain != "light":
                continue

            current_brightness = state.attributes.get("brightness", 0) or 0
            current_pct = round(current_brightness / 255 * 100)
            new_pct = max(0, min(100, current_pct + delta_pct))
            new_brightness = int(new_pct / 100 * 255)

            if new_brightness <= 0:
                await self.hass.services.async_call(
                    "light", SERVICE_TURN_OFF, {ATTR_ENTITY_ID: eid}, blocking=True
                )
            else:
                await self.hass.services.async_call(
                    "light",
                    SERVICE_TURN_ON,
                    {ATTR_ENTITY_ID: eid, "brightness": new_brightness},
                    blocking=True,
                )
            _LOGGER.debug(
                "Brightness adjust %s: %d%% → %d%%", eid, current_pct, new_pct
            )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize_targets(targets: Any) -> list[str]:
    """Return a flat list of entity_id strings from scalar, comma-separated, or list target."""
    if targets is None:
        return []
    if isinstance(targets, str):
        if not targets:
            return []
        if "," in targets:
            return [t.strip() for t in targets.split(",") if t.strip()]
        return [targets]
    if isinstance(targets, (list, tuple)):
        return [str(t) for t in targets if t]
    return [str(targets)]


def _entities_are_covers(entities: list[str]) -> bool:
    """Return True if any entity in the list is a cover."""
    return any(e.startswith("cover.") for e in entities)
