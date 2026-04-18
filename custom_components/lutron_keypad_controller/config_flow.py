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

    button_numbers: list[int] = sorted(
        {int(bd["button_number"]) for bd in matching if "button_number" in bd}
    )
    if not button_numbers:
        return {}

    raise_btn: int | None = None
    lower_btn: int | None = None
    for bd in matching:
        name  = bd.get("name", "").lower()
        bnum  = int(bd.get("button_number", -1))
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

# Maps action type → (entity domains, multiple)
_ACTION_DOMAINS: dict[str, tuple[list[str], bool]] = {
    "stateful_scene":  (["scene"],                                           False),
    "ha_scene":        (["scene"],                                           False),
    "automation":      (["automation"],                                      False),
    "script":          (["script"],                                          False),
    "entity_toggle":   (["light", "switch", "fan",
                         "input_boolean", "cover", "media_player"],         True),
    "cover_cycle":     (["cover"],                                           True),
    "light_cycle_dim": (["light"],                                           True),
}

_ACTION_OPTIONS = [
    {"value": "stateful_scene",  "label": "🎬 Stateful Scene"},
    {"value": "ha_scene",        "label": "💡 HA Scene"},
    {"value": "automation",      "label": "▶️ Automation"},
    {"value": "script",          "label": "📜 Script"},
    {"value": "entity_toggle",   "label": "🔀 Entity Toggle"},
    {"value": "cover_cycle",     "label": "🪟 Shade Cycle"},
    {"value": "light_cycle_dim", "label": "🔆 Dim Cycle"},
    {"value": "raise",           "label": "⬆️ Raise"},
    {"value": "lower",           "label": "⬇️ Lower"},
    {"value": "none",            "label": "➖ None"},
]


class LutronKeypadsOptionsFlow(config_entries.OptionsFlow):
    """Multi-step options wizard: button list → single-button edit or bulk edit."""

    def __init__(self) -> None:
        self._buttons_config: dict[str, dict] = {}
        self._current_btn: str = ""
        self._bulk_buttons: list[str] = []
        self._bulk_action: str = ACTION_NONE

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_all_buttons(self) -> list[dict]:
        return get_button_layout(self.config_entry.data)

    def _get_button_numbers(self) -> list[str]:
        return [str(b["number"]) for b in self._get_all_buttons()
                if not b["is_raise"] and not b["is_lower"]]

    def _get_current_buttons(self) -> dict:
        return dict(self.config_entry.options.get("buttons", {}))

    def _normalize_target(self, target: Any) -> list[str]:
        if isinstance(target, list):
            return [e.strip() for e in target if str(e).strip()]
        if isinstance(target, str) and target.strip():
            return [e.strip() for e in target.split(",") if e.strip()]
        return []

    def _build_init_schema(self) -> vol.Schema:
        keypad_name = self.config_entry.data.get("name", "Keypad")
        options: list[dict] = [
            {"value": "bulk_edit", "label": "✏️ Bulk Edit Multiple Buttons"},
        ]

        for btn in self._get_all_buttons():
            n = str(btn["number"])
            if btn["is_raise"]:
                options.append({"value": n, "label": f"Button {n} — ⬆️ Raise (fixed)"})
                continue
            if btn["is_lower"]:
                options.append({"value": n, "label": f"Button {n} — ⬇️ Lower (fixed)"})
                continue

            cfg = self._buttons_config.get(n, {})
            lbl = cfg.get("label", f"Button {n}")
            act = cfg.get(CONF_ACTION_TYPE, ACTION_NONE)
            tgt = self._normalize_target(cfg.get(CONF_ACTION_TARGET, ""))
            tgt_str = ", ".join(tgt) if tgt else ""
            if tgt_str:
                summary = f"Button {n} — {lbl}  [{act} → {tgt_str}]"
            else:
                summary = f"Button {n} — {lbl}  [{act}]"
            options.append({"value": n, "label": summary})

        options.append({"value": "save", "label": "✓ Save & Close"})

        return vol.Schema({
            vol.Required("selected_button", default="save"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    mode=selector.SelectSelectorMode.LIST,
                )
            )
        })

    def _build_button_type_schema(self, btn_num: str) -> vol.Schema:
        cfg = self._buttons_config.get(btn_num, {})
        return vol.Schema({
            vol.Optional("label", default=cfg.get("label", f"Button {btn_num}")): (
                selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                )
            ),
            vol.Required("action_type", default=cfg.get(CONF_ACTION_TYPE, ACTION_NONE)): (
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=_ACTION_OPTIONS,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            ),
        })

    def _build_entity_schema(self, btn_num: str) -> vol.Schema:
        cfg = self._buttons_config.get(btn_num, {})
        cur_action = cfg.get(CONF_ACTION_TYPE, ACTION_NONE)
        domains, multiple = _ACTION_DOMAINS[cur_action]
        raw_target = cfg.get(CONF_ACTION_TARGET, "")

        if multiple:
            default_target = self._normalize_target(raw_target)
        else:
            tgt_list = self._normalize_target(raw_target)
            default_target = tgt_list[0] if tgt_list else ""

        schema_dict: dict = {
            vol.Optional("action_target", default=default_target): (
                selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=domains, multiple=multiple)
                )
            ),
        }

        if cur_action == ACTION_STATEFUL_SCENE:
            cur_led = cfg.get(CONF_LED_ENTITY, "")
            schema_dict[vol.Optional("led_entity", default=cur_led)] = (
                selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["switch"], multiple=False)
                )
            )
            cur_sg = cfg.get("scene_group", "")
            schema_dict[vol.Optional("scene_group", default=cur_sg)] = (
                selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                )
            )

        return vol.Schema(schema_dict)

    # ── Step 1 — Button list ──────────────────────────────────────────────────

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if not self._buttons_config:
            existing = self._get_current_buttons()
            all_btns = self._get_all_buttons()
            for btn in all_btns:
                n = str(btn["number"])
                if btn["is_raise"]:
                    self._buttons_config[n] = {"label": "Raise", CONF_ACTION_TYPE: ACTION_RAISE}
                elif btn["is_lower"]:
                    self._buttons_config[n] = {"label": "Lower", CONF_ACTION_TYPE: ACTION_LOWER}
                else:
                    self._buttons_config[n] = dict(existing.get(n, {}))

        if user_input is not None:
            selected = user_input.get("selected_button", "save")
            if selected == "save":
                return self.async_create_entry(title="", data={"buttons": self._buttons_config})
            if selected == "bulk_edit":
                return await self.async_step_bulk()
            # Fixed raise/lower buttons are not editable
            btn_obj = next(
                (b for b in self._get_all_buttons() if str(b["number"]) == selected),
                None,
            )
            if btn_obj and (btn_obj["is_raise"] or btn_obj["is_lower"]):
                return await self.async_step_init()
            self._current_btn = selected
            return await self.async_step_button()

        keypad_name = self.config_entry.data.get("name", "Keypad")
        return self.async_show_form(
            step_id="init",
            data_schema=self._build_init_schema(),
            description_placeholders={"name": keypad_name},
        )

    # ── Step 2 — Label + action type ─────────────────────────────────────────

    async def async_step_button(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        btn_num = self._current_btn
        keypad_name = self.config_entry.data.get("name", "Keypad")

        if user_input is not None:
            new_type = user_input.get("action_type", ACTION_NONE)
            old_cfg  = self._buttons_config.get(btn_num, {})

            self._buttons_config[btn_num] = {
                **old_cfg,
                "label":          user_input.get("label", f"Button {btn_num}"),
                CONF_ACTION_TYPE: new_type,
            }

            if new_type in _ACTION_DOMAINS:
                return await self.async_step_entity()

            # No entity needed — clear any stale target and go back to list
            self._buttons_config[btn_num][CONF_ACTION_TARGET] = []
            self._buttons_config[btn_num][CONF_LED_ENTITY] = ""
            self._buttons_config[btn_num]["scene_group"] = ""
            return await self.async_step_init()

        return self.async_show_form(
            step_id="button",
            data_schema=self._build_button_type_schema(btn_num),
            description_placeholders={
                "button_number": btn_num,
                "keypad_name":   keypad_name,
            },
        )

    # ── Step 3 — Entity selection ─────────────────────────────────────────────

    async def async_step_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        btn_num = self._current_btn
        keypad_name = self.config_entry.data.get("name", "Keypad")
        cur_action  = self._buttons_config.get(btn_num, {}).get(CONF_ACTION_TYPE, ACTION_NONE)

        if user_input is not None:
            raw_target = user_input.get("action_target", "")
            self._buttons_config[btn_num][CONF_ACTION_TARGET] = (
                self._normalize_target(raw_target)
            )
            self._buttons_config[btn_num][CONF_LED_ENTITY] = (
                user_input.get("led_entity", "")
            )
            sg = user_input.get("scene_group", "")
            self._buttons_config[btn_num]["scene_group"] = (
                sg.strip() if isinstance(sg, str) else ""
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id="entity",
            data_schema=self._build_entity_schema(btn_num),
            description_placeholders={
                "button_number": btn_num,
                "keypad_name":   keypad_name,
                "action_type":   cur_action,
            },
        )

    # ── Step 4 — Bulk edit: pick buttons + action type ────────────────────────

    async def async_step_bulk(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        keypad_name = self.config_entry.data.get("name", "Keypad")

        if user_input is not None:
            self._bulk_buttons = user_input.get("button_numbers", [])
            self._bulk_action  = user_input.get("action_type", ACTION_NONE)

            if not self._bulk_buttons:
                return await self.async_step_init()

            if self._bulk_action in _ACTION_DOMAINS:
                return await self.async_step_bulk_entity()

            # No entity needed — apply action type immediately and clear targets
            for n in self._bulk_buttons:
                old_cfg = self._buttons_config.get(n, {})
                self._buttons_config[n] = {
                    **old_cfg,
                    CONF_ACTION_TYPE:   self._bulk_action,
                    CONF_ACTION_TARGET: [],
                    CONF_LED_ENTITY:    "",
                    "scene_group":      "",
                }
            return await self.async_step_init()

        configurable = self._get_button_numbers()
        btn_options = [
            {
                "value": n,
                "label": f"Button {n}: {self._buttons_config.get(n, {}).get('label', f'Button {n}')}",
            }
            for n in configurable
        ]

        schema = vol.Schema({
            vol.Required("button_numbers"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=btn_options,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Required("action_type", default=ACTION_NONE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_ACTION_OPTIONS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        })

        return self.async_show_form(
            step_id="bulk",
            data_schema=schema,
            description_placeholders={"keypad_name": keypad_name},
        )

    # ── Step 5 — Bulk edit: entity selection ──────────────────────────────────

    async def async_step_bulk_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        keypad_name  = self.config_entry.data.get("name", "Keypad")
        bulk_action  = self._bulk_action
        domains, multiple = _ACTION_DOMAINS[bulk_action]

        if user_input is not None:
            raw_target  = user_input.get("action_target", "")
            target      = self._normalize_target(raw_target)
            scene_group = user_input.get("scene_group", "")

            for n in self._bulk_buttons:
                old_cfg = self._buttons_config.get(n, {})
                self._buttons_config[n] = {
                    **old_cfg,
                    CONF_ACTION_TYPE:   bulk_action,
                    CONF_ACTION_TARGET: target,
                    "scene_group": scene_group.strip() if isinstance(scene_group, str) else "",
                }
            return await self.async_step_init()

        schema_dict: dict = {
            vol.Optional("action_target"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=domains, multiple=multiple)
            ),
        }
        if bulk_action == ACTION_STATEFUL_SCENE:
            schema_dict[vol.Optional("scene_group", default="")] = selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            )

        return self.async_show_form(
            step_id="bulk_entity",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "keypad_name":   keypad_name,
                "action_type":   bulk_action,
                "button_count":  str(len(self._bulk_buttons)),
            },
        )
