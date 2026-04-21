"""Constants for the Lutron Keypad Controller integration."""

DOMAIN = "lutron_keypad_controller"

# ── Event names ──────────────────────────────────────────────────────────────
LUTRON_EVENT = "lutron_caseta_button_event"

# ── Config / storage keys ────────────────────────────────────────────────────
CONF_DEVICE_SERIAL   = "device_serial"
CONF_DEVICE_NAME     = "device_name"
CONF_AREA_NAME       = "area_name"
CONF_KEYPAD_TYPE     = "keypad_type"
CONF_BUTTONS         = "buttons"

# Per-button keys
CONF_BUTTON_NUMBER   = "button_number"
CONF_BUTTON_LABEL    = "label"
CONF_ACTION_TYPE     = "action_type"
CONF_ACTION_TARGET   = "action_target"
CONF_ACTION_PARAMS   = "action_params"
CONF_LED_ENTITY        = "led_entity"
CONF_LED_INVERT        = "led_invert"
CONF_LED_MODE          = "led_mode"
CONF_TARGET_BRIGHTNESS = "target_brightness"   # 1-100 %, 0 = not set
CONF_TARGET_COLOR_TEMP = "target_color_temp"   # Kelvin, 0 = not set

# LED mode values (entity_toggle buttons)
LED_MODE_ROOM  = "room"   # ON when ANY assigned entity is on
LED_MODE_SCENE = "scene"  # ON when ALL assigned entities are on

# ── Keypad models ─────────────────────────────────────────────────────────────
KEYPAD_SEETOUCH          = "seetouch"
KEYPAD_SEETOUCH_HYBRID   = "seetouch_hybrid"
KEYPAD_SUNNATA           = "sunnata"
KEYPAD_SUNNATA_HYBRID    = "sunnata_hybrid"
KEYPAD_ALISEE            = "alisee"
KEYPAD_PALLADIOM         = "palladiom"
KEYPAD_TABLETOP          = "tabletop"
KEYPAD_PICO              = "pico"
KEYPAD_GENERIC           = "generic"

KEYPAD_TYPES = [
    KEYPAD_SEETOUCH,
    KEYPAD_SEETOUCH_HYBRID,
    KEYPAD_SUNNATA,
    KEYPAD_SUNNATA_HYBRID,
    KEYPAD_ALISEE,
    KEYPAD_PALLADIOM,
    KEYPAD_TABLETOP,
    KEYPAD_PICO,
    KEYPAD_GENERIC,
]

RAISE_LOWER_BUTTON_TYPES = {
    "raise": [3, 5, 7, 17, 19],
    "lower": [4, 6, 8, 18, 20],
}

# ── Action types ──────────────────────────────────────────────────────────────
ACTION_STATEFUL_SCENE  = "stateful_scene"
ACTION_HA_SCENE        = "ha_scene"
ACTION_AUTOMATION      = "automation"
ACTION_SCRIPT          = "script"
ACTION_ENTITY_TOGGLE   = "entity_toggle"
ACTION_COVER_CYCLE     = "cover_cycle"
ACTION_LIGHT_CYCLE_DIM = "light_cycle_dim"
ACTION_RAISE           = "raise"
ACTION_LOWER           = "lower"
ACTION_NONE            = "none"

ACTION_TYPES = [
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

# ── Stateful scene tracking ───────────────────────────────────────────────────
ATTR_ACTIVE_SCENE    = "active_scene"
ATTR_LAST_ACTION     = "last_action"
ATTR_COVER_STATES    = "cover_states"
ATTR_LIGHT_DIM_STEPS = "light_dim_steps"

DIM_CYCLE_LEVELS = [100, 75, 50, 25]

COVER_STATE_OPEN  = "open"
COVER_STATE_STOP  = "stop"
COVER_STATE_CLOSE = "close"

RAISE_LOWER_STEP = 10

SENSOR_SUFFIX_STATUS     = "status"
SENSOR_SUFFIX_LAST_BTN   = "last_button"

# ── Action type friendly labels ───────────────────────────────────────────────
ACTION_TYPE_LABELS: dict[str, str] = {
    ACTION_STATEFUL_SCENE:  "Stateful Scene",
    ACTION_HA_SCENE:        "HA Scene",
    ACTION_AUTOMATION:      "Automation",
    ACTION_SCRIPT:          "Script",
    ACTION_ENTITY_TOGGLE:   "Entity Toggle",
    ACTION_COVER_CYCLE:     "Cover Cycle",
    ACTION_LIGHT_CYCLE_DIM: "Dim Cycle",
    ACTION_RAISE:           "Raise",
    ACTION_LOWER:           "Lower",
    ACTION_NONE:            "None",
}
ACTION_LABEL_TO_TYPE: dict[str, str] = {v: k for k, v in ACTION_TYPE_LABELS.items()}

# ── Action type → allowed entity domains ─────────────────────────────────────
ACTION_TYPE_DOMAINS: dict[str, list[str]] = {
    ACTION_STATEFUL_SCENE:  ["scene"],
    ACTION_HA_SCENE:        ["scene"],
    ACTION_AUTOMATION:      ["automation"],
    ACTION_SCRIPT:          ["script"],
    ACTION_ENTITY_TOGGLE:   ["light", "switch", "fan", "input_boolean", "media_player", "cover"],
    ACTION_COVER_CYCLE:     ["cover"],
    ACTION_LIGHT_CYCLE_DIM: ["light"],
    ACTION_RAISE:           [],
    ACTION_LOWER:           [],
    ACTION_NONE:            [],
}

MULTI_ENTITY_ACTIONS: frozenset[str] = frozenset({
    ACTION_ENTITY_TOGGLE,
    ACTION_COVER_CYCLE,
    ACTION_LIGHT_CYCLE_DIM,
})

ACTION_TYPES_NEEDING_ENTITY: frozenset[str] = frozenset(
    k for k, v in ACTION_TYPE_DOMAINS.items() if v
)

# ── Per-keypad button layout ──────────────────────────────────────────────────
# (main_button_count, has_raise_lower)
KEYPAD_LAYOUTS: dict[str, tuple[int, bool]] = {
    KEYPAD_SEETOUCH:        (6,  True),
    KEYPAD_SEETOUCH_HYBRID: (5,  True),
    KEYPAD_SUNNATA:         (4,  True),
    KEYPAD_SUNNATA_HYBRID:  (3,  True),
    KEYPAD_ALISEE:          (5,  True),
    KEYPAD_PALLADIOM:       (5,  True),
    KEYPAD_TABLETOP:        (10, False),
    KEYPAD_PICO:            (3,  False),
    KEYPAD_GENERIC:         (6,  True),
}


def get_button_list(keypad_type: str) -> list[dict]:
    """Return ordered button descriptors for the given keypad type."""
    main_count, has_rl = KEYPAD_LAYOUTS.get(keypad_type, KEYPAD_LAYOUTS[KEYPAD_GENERIC])
    buttons = [
        {"number": i, "is_raise": False, "is_lower": False}
        for i in range(1, main_count + 1)
    ]
    if has_rl:
        buttons.append({"number": main_count + 1, "is_raise": True,  "is_lower": False})
        buttons.append({"number": main_count + 2, "is_raise": False, "is_lower": True})
    return buttons


def get_button_layout(entry_data: dict) -> list[dict]:
    """Return button descriptors using bridge-detected data, falling back to keypad type map."""
    button_numbers = entry_data.get("button_numbers")
    if button_numbers:
        raise_btn = entry_data.get("raise_button")
        lower_btn = entry_data.get("lower_button")
        return [
            {
                "number": n,
                "is_raise": n == raise_btn,
                "is_lower": n == lower_btn,
            }
            for n in sorted(button_numbers)
        ]
    return get_button_list(entry_data.get(CONF_KEYPAD_TYPE, KEYPAD_GENERIC))
