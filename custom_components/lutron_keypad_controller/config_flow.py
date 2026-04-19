"""Config flow for Lutron Keypad Controller."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_DEVICE_SERIAL,
    CONF_DEVICE_NAME,
    CONF_AREA_NAME,
    CONF_KEYPAD_TYPE,
    CONF_ACTION_TYPE,
    CONF_ACTION_TARGET,
    CONF_LED_ENTITY,
    ACTION_STATEFUL_SCENE,
    KEYPAD_SEETOUCH,
    KEYPAD_SEETOUCH_HYBRID,
    KEYPAD_SUNNATA,
    KEYPAD_SUNNATA_HYBRID,
    KEYPAD_ALISEE,
    KEYPAD_PALLADIOM,
    KEYPAD_TABLETOP,
    KEYPAD_PICO,
    KEYPAD_GENERIC,
    ACTION_NONE,
    ACTION_RAISE,
    ACTION_LOWER,
    ACTION_TYPE_LABELS,
    ACTION_TYPE_DOMAINS,
    ACTION_TYPES_NEEDING_ENTITY,
    MULTI_ENTITY_ACTIONS,
    get_button_list,
    get_button_layout,
)

_LOGGER = logging.getLogger(__name__)

# ── Lutron device-type string → our keypad type ───────────────────────────────
LUTRON_TYPE_MAP: dict[str, str] = {
    "SeeTouchKeypad":               KEYPAD_SEETOUCH,
    "SeeTouchHybridKeypad":         KEYPAD_SEETOUCH_HYBRID,
    "HybridSeeTouch":               KEYPAD_SEETOUCH_HYBRID,
    "SeeTouch":                     KEYPAD_SEETOUCH,
    "SunnataKeypad":                KEYPAD_SUNNATA,
    "SunnataHybridKeypad":          KEYPAD_SUNNATA_HYBRID,
    "SunnataSwitchingKeypad":       KEYPAD_SUNNATA,
    "Sunnata":                      KEYPAD_SUNNATA,
    "AliseeKeypad":                 KEYPAD_ALISEE,
    "Alisee":                       KEYPAD_ALISEE,
    "PalladiomKeypad":              KEYPAD_PALLADIOM,
    "Palladiom":                    KEYPAD_PALLADIOM,
    "PalladiomWirelessKeypad":      KEYPAD_PALLADIOM,
    "TabletopSeeTouch":             KEYPAD_TABLETOP,
    "SeeTouchTabletop":             KEYPAD_TABLETOP,
    "TabletopKeypad":               KEYPAD_TABLETOP,
    "Pico1Button":                  KEYPAD_PICO,
    "Pico2Button":                  KEYPAD_PICO,
    "Pico2ButtonRaiseLower":        KEYPAD_PICO,
    "Pico3Button":                  KEYPAD_PICO,
    "Pico3ButtonRaiseLower":        KEYPAD_PICO,
    "Pico4Button":                  KEYPAD_PICO,
    "Pico4ButtonScene":             KEYPAD_PICO,
    "Pico4ButtonZone":              KEYPAD_PICO,
    "Pico4Button2Group":            KEYPAD_PICO,
    "FourGroupRemote":              KEYPAD_PICO,
    "PaddleRemote":                 KEYPAD_PICO,
}

LUTRON_TYPE_FUZZY: list[tuple[str, str]] = [
    ("hybrid",     KEYPAD_SEETOUCH_HYBRID),
    ("seetouch",   KEYPAD_SEETOUCH),
    ("sunnata",    KEYPAD_SUNNATA),
    ("alisee",     KEYPAD_ALISEE),
    ("palladiom",  KEYPAD_PALLADIOM),
    ("tabletop",   KEYPAD_TABLETOP),
    ("pico",       KEYPAD_PICO),
    ("remote",     KEYPAD_PICO),
    ("keypad",     KEYPAD_SEETOUCH),
]

BUTTON_TYPE_KEYWORDS = {
    "keypad", "pico", "remote", "seetouch", "sunnata",
    "alisee", "palladiom", "tabletop", "hybrid",
}


def _infer_keypad_type(device_type: str) -> str:
    if device_type in LUTRON_TYPE_MAP:
        return LUTRON_TYPE_MAP[device_type]
    lower = device_type.lower()
    for keyword, kp_type in LUTRON_TYPE_FUZZY:
        if keyword in lower:
            return kp_type
    return KEYPAD_GENERIC


def _is_keypad_device(device: dict) -> bool:
    device_type: str = device.get("type", "")
    if device_type in LUTRON_TYPE_MAP:
        return True
    lower = device_type.lower()
    return any(kw in lower for kw in BUTTON_TYPE_KEYWORDS)


def _get_lutron_bridge(hass: HomeAssistant):
    for entry in hass.config_entries.async_entries("lutron_caseta"):
        if entry.state is not ConfigEntryState.LOADED:
            continue
        runtime = getattr(entry, "runtime_data", None)
        if runtime is not None:
            bridge = getattr(runtime, "bridge", None)
            if bridge is not None:
                return bridge
        entry_data = hass.data.get("lutron_caseta", {}).get(entry.entry_id)
        if entry_data is not None:
            bridge = getattr(entry_data, "bridge", None)
            if bridge is None and isinstance(entry_data, dict):
                bridge = entry_data.get("bridge")
            if bridge is not None:
                return bridge
    return None


def _discover_keypads(hass: HomeAssistant) -> list[dict]:
    bridge = _get_lutron_bridge(hass)
    if bridge is None:
        return []
    try:
        all_devices: dict = bridge.get_devices()
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("Could not query Lutron bridge devices: %s", exc)
        return []
    keypads = [d for d in all_devices.values() if _is_keypad_device(d)]
    keypads.sort(key=lambda d: (d.get("area_name", ""), d.get("name", "")))
    return keypads


def _build_device_options(keypads: list[dict]) -> dict[str, str]:
    options: dict[str, str] = {}
    for device in keypads:
        serial = str(device.get("serial", ""))
        if not serial:
            continue
        area  = device.get("area_name", "Unknown Area")
        name  = device.get("name", "Unknown")
        ktype = _infer_keypad_type(device.get("type", ""))
        options[serial] = f"{area} — {name}  [{ktype}]"
    return options


def _resolve_btn_num(bd: dict) -> int | None:
    """Return a button's number, preferring leap_button_number when button_number is null."""
    for key in ("button_number", "leap_button_number"):
        raw = bd.get(key)
        if raw is not None:
            try:
                return int(raw)
            except (TypeError, ValueError):
                pass
    return None


def _detect_button_layout(hass: HomeAssistant, serial: str, keypad_type: str) -> dict:
    """Query bridge.button_devices for the actual buttons on this device.

    Returns a dict with button_numbers / configurable_buttons / raise_button /
    lower_button to be stored in config entry data.  Returns {} on failure so
    the caller falls back to the family-based count.
    """
    bridge = _get_lutron_bridge(hass)
    if bridge is None:
        return {}

    button_devices: dict = getattr(bridge, "button_devices", None) or {}
    if not button_devices:
        _LOGGER.warning(
            "bridge.button_devices not available for serial %s; using fallback button count",
            serial,
        )
        return {}

    matching = [
        bd for bd in button_devices.values()
        if str(bd.get("serial", "")) == serial
    ]
    if not matching:
        _LOGGER.warning(
            "No button_devices matched serial %s; using fallback button count", serial
        )
        return {}

    button_numbers: list[int] = sorted({
        n for bd in matching
        if (n := _resolve_btn_num(bd)) is not None
    })
    if not button_numbers:
        return {}

    raise_btn: int | None = None
    lower_btn: int | None = None
    for bd in matching:
        name = bd.get("name", "").lower()
        bnum = _resolve_btn_num(bd)
        if bnum is None:
            continue
        if name.endswith((" raise", "-raise", " up", "-up")):
            raise_btn = bnum
        elif name.endswith((" lower", "-lower", " down", "-down")):
            lower_btn = bnum

    configurable = [n for n in button_numbers if n not in (raise_btn, lower_btn)]

    _LOGGER.debug(
        "Detected %d button(s) for serial %s: configurable=%s raise=%s lower=%s",
        len(button_numbers), serial, configurable, raise_btn, lower_btn,
    )
    return {
        "button_numbers":      button_numbers,
        "configurable_buttons": configurable,
        "raise_button":        raise_btn,
        "lower_button":        lower_btn,
    }


# ── Config Flow ───────────────────────────────────────────────────────────────

class LutronKeypadsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Lutron Keypad Controller."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered_keypads: list[dict] = []
        self._selected_device: dict | None = None
        self._detected_layout: dict = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        lutron_entries = self.hass.config_entries.async_entries("lutron_caseta")
        if not lutron_entries:
            return self.async_abort(reason="lutron_not_loaded")

        if not self._discovered_keypads:
            self._discovered_keypads = await self.hass.async_add_executor_job(
                _discover_keypads, self.hass
            )

        if not self._discovered_keypads:
            return await self.async_step_manual()

        device_options = _build_device_options(self._discovered_keypads)
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_serial = user_input.get("device_serial", "")
            self._selected_device = next(
                (d for d in self._discovered_keypads
                 if str(d.get("serial", "")) == selected_serial),
                None,
            )
            if self._selected_device is None:
                errors["base"] = "device_not_found"
            else:
                await self.async_set_unique_id(selected_serial)
                self._abort_if_unique_id_configured()
                # Detect actual button layout from bridge
                serial      = str(self._selected_device.get("serial", ""))
                ktype       = _infer_keypad_type(self._selected_device.get("type", ""))
                self._detected_layout = _detect_button_layout(self.hass, serial, ktype)
                return await self.async_step_confirm()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required("device_serial"): vol.In(device_options)}
            ),
            errors=errors,
            description_placeholders={"count": str(len(self._discovered_keypads))},
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        device = self._selected_device
        if device is None:
            return await self.async_step_user()

        device_type    = device.get("type", "")
        keypad_type    = _infer_keypad_type(device_type)
        area_name      = device.get("area_name", "")
        device_name    = device.get("name", "")
        serial         = str(device.get("serial", ""))
        suggested_name = f"{area_name} — {device_name}" if area_name else device_name

        if user_input is not None:
            friendly_name = user_input.get("name", suggested_name).strip()
            return self.async_create_entry(
                title=friendly_name,
                data={
                    "name":             friendly_name,
                    CONF_DEVICE_SERIAL: serial,
                    CONF_DEVICE_NAME:   device_name,
                    CONF_AREA_NAME:     area_name,
                    CONF_KEYPAD_TYPE:   keypad_type,
                    "lutron_type":      device_type,
                    "device_id":        device.get("device_id", ""),
                    **self._detected_layout,
                },
            )

        btn_nums = self._detected_layout.get("button_numbers", [])
        if btn_nums:
            btn_str = f"{len(btn_nums)} buttons detected from bridge"
        else:
            fallback = get_button_list(keypad_type)
            btn_str  = f"{len(fallback)} buttons (estimated from keypad type)"

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {vol.Required("name", default=suggested_name): str}
            ),
            description_placeholders={
                "area":         area_name or "—",
                "device_name":  device_name,
                "keypad_type":  keypad_type,
                "serial":       serial,
                "lutron_type":  device_type,
                "button_count": btn_str,
            },
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            serial = user_input.get(CONF_DEVICE_SERIAL, "").strip()
            if not serial:
                errors[CONF_DEVICE_SERIAL] = "serial_required"
            else:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
                name = user_input.get("name", serial).strip()
                return self.async_create_entry(
                    title=name,
                    data={
                        "name":             name,
                        CONF_DEVICE_SERIAL: serial,
                        CONF_DEVICE_NAME:   user_input.get(CONF_DEVICE_NAME, ""),
                        CONF_AREA_NAME:     user_input.get(CONF_AREA_NAME, ""),
                        CONF_KEYPAD_TYPE:   KEYPAD_GENERIC,
                        "lutron_type":      "",
                    },
                )

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Required(CONF_DEVICE_SERIAL): str,
                    vol.Optional(CONF_DEVICE_NAME, default=""): str,
                    vol.Optional(CONF_AREA_NAME, default=""): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "note": (
                    "Auto-discovery failed — the Lutron bridge may not be "
                    "reachable yet. Enter the serial manually: press any "
                    "button on the keypad and check "
                    "Developer Tools → Events → lutron_caseta_button_event."
                )
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return LutronKeypadsOptionsFlow()


# ── Options Flow ──────────────────────────────────────────────────────────────

_ACTION_OPTIONS = [
    {"value": k, "label": v}
    for k, v in ACTION_TYPE_LABELS.items()
]


class LutronKeypadsOptionsFlow(config_entries.OptionsFlow):
    """Two-step options wizard matching the rfwc5 pattern.

    Step 1 (buttons): all configurable buttons shown at once — label + action type.
    Step 2 (entities): entity pickers for every button that needs a target.
    """

    def __init__(self) -> None:
        self._buttons_config: dict[int, dict] = {}

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_all_buttons(self) -> list[dict]:
        return get_button_layout(self.config_entry.data)

    def _get_configurable(self) -> list[dict]:
        return [b for b in self._get_all_buttons() if not b["is_raise"] and not b["is_lower"]]

    def _get_raise_lower_note(self) -> str:
        parts = []
        for b in self._get_all_buttons():
            if b["is_raise"]:
                parts.append(f"Button {b['number']} (Raise)")
            elif b["is_lower"]:
                parts.append(f"Button {b['number']} (Lower)")
        if not parts:
            return ""
        return f"{', '.join(parts)} are fixed raise/lower buttons and cannot be reassigned."

    def _normalize_target(self, target: Any) -> list[str]:
        if isinstance(target, list):
            return [str(e).strip() for e in target if str(e).strip()]
        if isinstance(target, str) and target.strip():
            return [e.strip() for e in target.split(",") if e.strip()]
        return []

    def _default_entity(self, cfg: dict, multiple: bool) -> Any:
        raw = cfg.get(CONF_ACTION_TARGET, "")
        if multiple:
            return raw if isinstance(raw, list) else self._normalize_target(raw)
        if isinstance(raw, list):
            return raw[0] if raw else ""
        return raw or ""

    # ── Step 1 — Configure all buttons ───────────────────────────────────────

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_step_buttons(user_input)

    async def async_step_buttons(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        # Seed from existing options on first visit
        if not self._buttons_config:
            saved = self.config_entry.options.get("buttons", {})
            for k, v in saved.items():
                try:
                    self._buttons_config[int(k)] = dict(v)
                except (ValueError, TypeError):
                    pass

        configurable = self._get_configurable()
        keypad_name = self.config_entry.data.get("name", "Keypad")

        if user_input is not None:
            for btn in configurable:
                n = btn["number"]
                old_cfg = self._buttons_config.get(n, {})
                new_action = user_input.get(f"button_{n}_action_type", ACTION_NONE)
                self._buttons_config[n] = {
                    **old_cfg,
                    "label": user_input.get(f"button_{n}_label", f"Button {n}"),
                    CONF_ACTION_TYPE: new_action,
                }
                if new_action not in ACTION_TYPES_NEEDING_ENTITY:
                    self._buttons_config[n][CONF_ACTION_TARGET] = []
                    self._buttons_config[n][CONF_LED_ENTITY] = ""
                    self._buttons_config[n]["scene_group"] = ""

            # Preserve raise/lower entries
            for btn in self._get_all_buttons():
                if btn["is_raise"]:
                    self._buttons_config[btn["number"]] = {"label": "Raise", CONF_ACTION_TYPE: ACTION_RAISE}
                elif btn["is_lower"]:
                    self._buttons_config[btn["number"]] = {"label": "Lower", CONF_ACTION_TYPE: ACTION_LOWER}

            needs_entity = any(
                self._buttons_config.get(b["number"], {}).get(CONF_ACTION_TYPE) in ACTION_TYPES_NEEDING_ENTITY
                for b in configurable
            )
            if needs_entity:
                return await self.async_step_entities()
            return self.async_create_entry(
                title="",
                data={"buttons": {str(k): v for k, v in self._buttons_config.items()}},
            )

        schema_dict: dict = {}
        for btn in configurable:
            n = btn["number"]
            cfg = self._buttons_config.get(n, {})
            schema_dict[vol.Optional(f"button_{n}_label", default=cfg.get("label", f"Button {n}"))] = (
                selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT))
            )
            schema_dict[vol.Required(f"button_{n}_action_type", default=cfg.get(CONF_ACTION_TYPE, ACTION_NONE))] = (
                selector.SelectSelector(selector.SelectSelectorConfig(
                    options=_ACTION_OPTIONS,
                    mode=selector.SelectSelectorMode.LIST,
                ))
            )

        return self.async_show_form(
            step_id="buttons",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "keypad_name":      keypad_name,
                "raise_lower_note": self._get_raise_lower_note(),
            },
        )

    # ── Step 2 — Entity assignment ────────────────────────────────────────────

    async def async_step_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        configurable = self._get_configurable()
        active = [
            b for b in configurable
            if self._buttons_config.get(b["number"], {}).get(CONF_ACTION_TYPE) in ACTION_TYPES_NEEDING_ENTITY
        ]
        keypad_name = self.config_entry.data.get("name", "Keypad")

        if not active:
            return self.async_create_entry(
                title="",
                data={"buttons": {str(k): v for k, v in self._buttons_config.items()}},
            )

        if user_input is not None:
            for btn in active:
                n = btn["number"]
                action_type = self._buttons_config[n][CONF_ACTION_TYPE]
                multiple = action_type in MULTI_ENTITY_ACTIONS
                raw = user_input.get(f"button_{n}_entity", [] if multiple else "")
                self._buttons_config[n][CONF_ACTION_TARGET] = (
                    (raw if isinstance(raw, list) else self._normalize_target(raw))
                    if multiple else raw
                )
                if action_type == ACTION_STATEFUL_SCENE:
                    self._buttons_config[n][CONF_LED_ENTITY] = user_input.get(f"button_{n}_led", "")
                    sg = user_input.get(f"button_{n}_scene_group", "")
                    self._buttons_config[n]["scene_group"] = sg.strip() if isinstance(sg, str) else ""

            return self.async_create_entry(
                title="",
                data={"buttons": {str(k): v for k, v in self._buttons_config.items()}},
            )

        schema_dict: dict = {}
        for btn in active:
            n = btn["number"]
            cfg = self._buttons_config.get(n, {})
            action_type = cfg.get(CONF_ACTION_TYPE, ACTION_NONE)
            domains = ACTION_TYPE_DOMAINS.get(action_type, [])
            multiple = action_type in MULTI_ENTITY_ACTIONS

            schema_dict[vol.Optional(f"button_{n}_entity", default=self._default_entity(cfg, multiple))] = (
                selector.EntitySelector(selector.EntitySelectorConfig(domain=domains, multiple=multiple))
            )
            if action_type == ACTION_STATEFUL_SCENE:
                schema_dict[vol.Optional(f"button_{n}_led", default=cfg.get(CONF_LED_ENTITY, ""))] = (
                    selector.EntitySelector(selector.EntitySelectorConfig(domain=["switch"], multiple=False))
                )
                schema_dict[vol.Optional(f"button_{n}_scene_group", default=cfg.get("scene_group", ""))] = (
                    selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT))
                )

        return self.async_show_form(
            step_id="entities",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={"keypad_name": keypad_name},
        )
