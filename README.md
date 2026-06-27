# Buttons Machine

**Buttons Machine** is a custom integration for **Ctrlable Pro** (Ctrlable's professional smart-home platform). It maps the physical buttons on your keypads to actions and drives each keypad's LED indicators so they reflect the real state of your system.

Program every button visually in a sidebar panel reminiscent of Lutron Designer — no processor re-programming required. Pick what each button does, bind its LED to the lights it controls, and Buttons Machine handles the dispatch and feedback inside Ctrlable Pro.

> Formerly named *Lutron Keypad Controller*.

---

## Supported Keypads

Keypads are grouped by the backend/transport that talks to them. Each backend is a separately licensed module (see [Licensing](#licensing)).

| Module | Transport | Keypads | Notes |
|--------|-----------|---------|-------|
| **Lutron Leap/Caséta** | LEAP protocol | SeeTouch, Hybrid SeeTouch, Sunnata, Hybrid Sunnata, Alisse/Alisée, Palladiom, Tabletop, Pico remotes | Lutron Caséta and RA2 Select systems. |
| **Lutron LIP** | LIP protocol | SeeTouch, Palladiom, Pico, Tabletop and similar QS keypads | Lutron Homeworks QS / RadioRA systems. Native hold and double-tap supported. Engraved button labels and raise/lower are auto-detected from the processor database. |
| **Eaton RFWC5** | Z-Wave | Eaton RFWC5 5-button scene keypad | Race-condition-free LED bitmask control. |

---

## Features

Every button is configured individually in the visual programming panel.

### Action Types

| Action | What it does |
|--------|--------------|
| **Stateful Scene** | Activates a scene and tracks it as the active scene for LED feedback. |
| **Scene** | Activates a plain scene with no state tracking. |
| **Automation** | Triggers an automation. |
| **Script** | Runs a script. |
| **Entity Toggle** | Toggles an entity, with Room Mode / Scene Mode LED logic. |
| **Cover Cycle** | Cycles a cover through open → stop → close. |
| **Dim Cycle** | Steps a light through configurable brightness levels. |
| **Raise / Lower** | Ramps lights or shades up or down. |
| **None** | Leaves the button unassigned. |

### LED Feedback

- Auto-discovers each keypad's LED entities and binds them to buttons.
- **Room mode** vs **Scene mode** LED behavior.
- **Invert** option per LED.
- Per-light target **brightness** and **color temperature**, auto-clamped to each light's supported range.

### Button Behaviors

- **Hold-to-Dim** — hold a button to ramp brightness.
- **Double-Tap** and **Hold** blocks for secondary actions.
- Configurable **fade** and **delay** timing.

### Programming Panel

A sidebar panel in Ctrlable Pro at the URL path `/buttons-machine`, modeled after Lutron Designer, where you configure every keypad, button, action, and LED binding.

---

## Installation

1. In **HACS**, add this repository as a **custom repository** and install **Buttons Machine**.
2. **Restart Ctrlable Pro.**
3. Add your keypads via **Settings → Devices & Services** (or the **"+"** button in the Buttons Machine panel).
4. Open the Buttons Machine panel's **License** dialog and apply a valid license for each module you use.

---

## Configuration

All configuration happens in the **Buttons Machine** sidebar panel (`/buttons-machine`):

1. Select a keypad. Its buttons and discovered LED entities appear automatically.
2. For each button, choose an **action type** and its target (scene, script, entities, etc.).
3. Bind the button's **LED**, set Room vs Scene mode, and configure any per-light brightness or color-temperature targets.
4. Add optional **Hold**, **Double-Tap**, or **Hold-to-Dim** behavior and adjust fade/delay timing.

For LIP keypads, engraved button labels and raise/lower buttons are auto-detected from the processor database, so most of the layout is filled in for you.

---

## Licensing

Buttons Machine uses per-module licensing through **portal.ctrlable.com**. Each backend module is licensed separately:

- **Lutron Leap/Caséta**
- **Lutron LIP**
- **Eaton RFWC5**

A valid, **instance-bound** license is required for each module in use. Apply licenses from the **License** dialog in the Buttons Machine panel.

> Existing legacy Lutron licenses continue to cover both **Caséta** and **LIP**.

---

## By Ctrlable

Buttons Machine is built and maintained by **Ctrlable** and runs on **Ctrlable Pro**.
