// ================================================================
// Lutron Keypad Programming Panel
// A custom HA panel element inspired by the Lutron Designer UI.
// ================================================================

const DOMAIN = "lutron_keypad_controller";

// ── Keypad layout geometry ────────────────────────────────────────
const KEYPAD_LAYOUTS = {
  seetouch:        { mainCount: 6, hasRL: true,  cols: 1 },
  seetouch_hybrid: { mainCount: 5, hasRL: true,  cols: 1 },
  sunnata:         { mainCount: 4, hasRL: true,  cols: 1 },
  sunnata_hybrid:  { mainCount: 3, hasRL: true,  cols: 1 },
  alisee:          { mainCount: 5, hasRL: false, cols: 1 },
  palladiom:       { mainCount: 5, hasRL: true,  cols: 1 },
  tabletop:        { mainCount: 10, hasRL: false, cols: 2 },
  pico:            { mainCount: 3,  hasRL: false, cols: 1 },
  generic:         { mainCount: 6,  hasRL: true,  cols: 1 },
};

/**
 * Parse the physical column layout from a keypad model number string.
 * Returns an array of per-column button counts, e.g. [4] or [3, 4].
 * Returns null when the model is unknown — caller falls back to KEYPAD_LAYOUTS.cols.
 *
 * Palladiom button config codes (per Lutron spec 369857r):
 *   Single char → 1-column: 2=2btn, 3=3btn, 4=4btn, R=3btn+Raise/Lower
 *   Two chars   → 2-column: each char = that column's config
 *   Model format: ...P{config}W...  e.g. HQWT-S-P44W, HQWT-S-PR4W
 *     PR4W → config=R4 → [3, 4]  (left: 3btn+RL, right: 4btn)
 *     P44W → config=44 → [4, 4]
 *     P4W  → config=4  → [4]
 *
 * Alisee  "2 Column (3B-3B)" → [3, 3]
 * SeeTouch "HQRD-W6BRL"     → [6]   (W + digits + B or S)
 */
function parsePhysicalColumns(model, keypadType) {
  if (!model) return null;
  if (keypadType === "alisee") {
    const m = model.match(/\((\d+B(?:-\d+B)*)\)/);
    if (m) return m[1].split("-").map(s => parseInt(s, 10));
  }
  if (keypadType === "palladiom") {
    // Config is 1-2 chars from [234R] between the letter P and trailing W
    const m = model.match(/P([2-4R]{1,2})W/);
    if (m) return m[1].split("").map(c => c === "R" ? 3 : parseInt(c, 10));
  }
  if (keypadType === "seetouch" || keypadType === "seetouch_hybrid") {
    // W{N}B or W{N}BS or W{N}S (S = scene with raise/lower)
    const m = model.match(/W(\d+)[BS]/);
    if (m) return [parseInt(m[1], 10)];
  }
  return null;
}

// ── Action types ──────────────────────────────────────────────────
const ACTION_TYPES = {
  none:            { label: "None",           domains: [],       multi: false },
  stateful_scene:  { label: "Stateful Scene", domains: ["scene"],       multi: false },
  ha_scene:        { label: "HA Scene",       domains: ["scene"],       multi: false },
  automation:      { label: "Automation",     domains: ["automation"],  multi: false },
  script:          { label: "Script",         domains: ["script"],      multi: false },
  entity_toggle:   { label: "Entity Toggle",  domains: ["light","switch","fan","input_boolean","media_player","cover"], multi: true },
  cover_cycle:     { label: "Cover Cycle",    domains: ["cover"],       multi: true },
  light_cycle_dim: { label: "Dim Cycle",      domains: ["light"],       multi: true },
  raise:           { label: "Raise",          domains: [],              multi: false },
  lower:           { label: "Lower",          domains: [],              multi: false },
};

// ── LED Logic options ─────────────────────────────────────────────
const LED_LOGIC = {
  room:  "Room",
  scene: "Scene",
  none:  "No Integration",
};

// ── Entity-domain display labels ──────────────────────────────────
const DOMAIN_LABELS = {
  scene: "Scene", light: "Light", switch: "Switch",
  cover: "Cover", automation: "Auto", script: "Script",
  fan: "Fan", media_player: "Media", input_boolean: "Boolean",
};

// ── CSS ───────────────────────────────────────────────────────────
const STYLES = `
  :host {
    display: flex;
    flex-direction: column;
    height: 100%;
    font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
    font-size: 14px;
    color: var(--primary-text-color, #212121);
    background: var(--secondary-background-color, #f0f2f5);
    overflow: hidden;
  }

  /* ── Top nav bar ── */
  .panel-header {
    display: flex;
    align-items: center;
    background: #1a3d2b;
    color: #fff;
    padding: 0 16px;
    height: 56px;
    flex-shrink: 0;
    gap: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.3);
    z-index: 10;
  }
  .panel-header .logo { font-size: 18px; font-weight: 500; letter-spacing: 0.5px; color: #81c784; }
  .panel-header .subtitle { font-size: 12px; color: #a5d6a7; flex: 1; padding-left: 8px; }
  .btn-save {
    background: #2e7d32; color: #fff; border: none; border-radius: 4px;
    padding: 8px 20px; font-size: 13px; font-weight: 500; cursor: pointer; transition: background 0.2s;
  }
  .btn-save:hover { background: #388e3c; }
  .btn-save:disabled { background: #555; cursor: default; }
  .save-status { font-size: 12px; color: #a5d6a7; min-width: 120px; text-align: right; }

  /* ── Body layout ── */
  .panel-body { display: flex; flex: 1; overflow: hidden; }

  /* ── Resize handles ── */
  .resize-handle-v {
    width: 5px; cursor: ew-resize;
    background: var(--divider-color, #e0e0e0);
    flex-shrink: 0; transition: background 0.15s; user-select: none;
  }
  .resize-handle-v:hover, .resize-handle-v.dragging { background: #4caf50; }
  .resize-handle-h {
    height: 5px; cursor: ns-resize;
    background: var(--divider-color, #e0e0e0);
    flex-shrink: 0; transition: background 0.15s; user-select: none;
  }
  .resize-handle-h:hover, .resize-handle-h.dragging { background: #4caf50; }

  /* ── Left sidebar ── */
  .sidebar {
    width: 220px; min-width: 140px;
    background: #1e2a22; color: #c8e6c9;
    display: flex; flex-direction: column; overflow: hidden; flex-shrink: 0;
  }
  .sidebar-header {
    padding: 10px 14px 8px; font-size: 11px; font-weight: 600;
    letter-spacing: 1px; text-transform: uppercase; color: #81c784;
    border-bottom: 1px solid #2d4a35;
    display: flex; align-items: center; justify-content: space-between;
  }
  .btn-add-keypad {
    background: rgba(76,175,80,0.2); border: 1px solid #4caf50; color: #81c784;
    border-radius: 4px; width: 22px; height: 22px; font-size: 16px; line-height: 1;
    cursor: pointer; display: flex; align-items: center; justify-content: center;
    flex-shrink: 0; transition: background 0.15s;
  }
  .btn-add-keypad:hover { background: rgba(76,175,80,0.4); }
  .sidebar-search-wrap {
    padding: 6px 10px; border-bottom: 1px solid #2d4a35;
  }
  .sidebar-search-wrap input {
    width: 100%; box-sizing: border-box; background: rgba(0,0,0,0.3);
    border: 1px solid #2d4a35; border-radius: 4px; color: #c8e6c9;
    padding: 4px 8px; font-size: 12px; outline: none;
  }
  .sidebar-search-wrap input::placeholder { color: #4a6a50; }
  .sidebar-search-wrap input:focus { border-color: #4caf50; }
  .sidebar-list { flex: 1; overflow-y: auto; padding: 4px 0; }
  .sidebar-area {
    padding: 6px 14px 2px; font-size: 10px; letter-spacing: 0.8px;
    text-transform: uppercase; color: #4caf50; font-weight: 600; margin-top: 4px;
  }
  .sidebar-entry {
    display: flex; flex-direction: column; padding: 8px 14px 8px 20px;
    cursor: pointer; border-left: 3px solid transparent; transition: background 0.15s; gap: 2px;
  }
  .sidebar-entry:hover { background: rgba(255,255,255,0.06); }
  .sidebar-entry.active { background: rgba(76,175,80,0.18); border-left-color: #4caf50; }
  .sidebar-entry .entry-name { font-size: 13px; color: #e8f5e9; font-weight: 500; }
  .sidebar-entry .entry-type {
    font-size: 10px; color: #81c784; background: rgba(76,175,80,0.2);
    border-radius: 3px; padding: 1px 5px; display: inline-block; width: fit-content;
  }
  .sidebar-entry .entry-model {
    font-size: 10px; color: #6a8f70; font-family: monospace;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }

  /* ── Main area ── */
  .main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
  .welcome {
    flex: 1; display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    color: var(--secondary-text-color, #757575); gap: 12px;
  }
  .welcome .welcome-icon { font-size: 64px; opacity: 0.3; }
  .welcome h2 { font-size: 22px; font-weight: 300; margin: 0; }
  .welcome p { font-size: 14px; margin: 0; }

  /* ── Breadcrumb ── */
  .breadcrumb {
    background: rgba(76,175,80,0.07); border-bottom: 1px solid rgba(76,175,80,0.2);
    padding: 6px 16px; font-size: 12px; color: #4caf50;
    flex-shrink: 0; display: flex; align-items: center; gap: 4px;
  }
  .breadcrumb span { color: #66bb6a; }

  /* ── Programming layout ── */
  .prog-body { display: flex; flex: 1; overflow: hidden; }

  /* ── Keypad column ── */
  .col-keypad {
    width: 186px; min-width: 120px; flex-shrink: 0;
    display: flex; flex-direction: column; align-items: center;
    padding: 12px; background: var(--card-background-color, #fff); overflow-y: auto; gap: 10px;
  }
  .kp-nav { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--secondary-text-color, #757575); }
  .kp-nav button {
    background: none; border: 1px solid var(--divider-color, #ccc);
    border-radius: 4px; padding: 2px 8px; cursor: pointer; font-size: 14px;
    color: var(--primary-text-color, #212121); transition: background 0.15s;
  }
  .kp-nav button:hover { background: rgba(76,175,80,0.1); border-color: #a5d6a7; }
  .kp-nav button:disabled { opacity: 0.3; cursor: default; }
  .kp-nav .btn-num { font-weight: 600; min-width: 48px; text-align: center; color: var(--primary-text-color); }

  /* ── Keypad device drawing ── */
  .keypad-device {
    background: #242424; border-radius: 10px; padding: 10px 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05);
    display: flex; flex-direction: column; align-items: center;
    gap: 6px; width: 140px; position: relative;
  }
  .keypad-device .kp-logo {
    font-size: 8px; color: #555; letter-spacing: 1px; text-transform: uppercase;
    align-self: flex-start; padding-left: 2px; margin-bottom: 2px;
  }
  .kp-main-buttons { display: flex; flex-direction: row; gap: 5px; width: 100%; }
  .kp-col { display: flex; flex-direction: column; gap: 5px; flex: 1; }
  .kp-btn {
    background: #3a3a3a; border: 1px solid #2a2a2a; border-radius: 4px;
    cursor: pointer; transition: all 0.15s;
    display: flex; align-items: center; justify-content: center;
    text-align: center; padding: 6px 4px; min-height: 32px;
    font-size: 9px; color: #bdbdbd; line-height: 1.2;
    box-shadow: inset 0 -2px 0 rgba(0,0,0,0.3), 0 1px 0 rgba(255,255,255,0.04);
    word-break: break-word; overflow: hidden;
  }
  .kp-btn:hover { background: #4a4a4a; color: #e0e0e0; }
  .kp-btn.selected {
    background: #2e7d32; color: #fff; border-color: #1b5e20;
    box-shadow: inset 0 -2px 0 rgba(0,0,0,0.3), 0 0 0 2px rgba(76,175,80,0.4);
  }
  .kp-btn.configured::after {
    content: "•"; color: #81c784;
    position: absolute; top: 2px; right: 3px; font-size: 8px;
  }
  .kp-btn.raise-lower {
    background: #2a2a2a; font-size: 12px; color: #666; min-height: 22px; padding: 2px;
  }
  .kp-btn.raise-lower:hover { color: #aaa; background: #333; }
  .kp-btn.raise-lower.selected { background: #1b5e20; color: #81c784; }
  .kp-btn { position: relative; }
  .kp-rl-row { display: flex; gap: 0; width: 100%; margin-top: 4px; border-radius: 4px; overflow: hidden; border: 1px solid #3a3a3a; }
  .kp-rl-row .kp-btn { flex: 1; border-radius: 0; border: none; border-right: 1px solid #3a3a3a; min-height: 20px; padding: 3px 2px; }
  .kp-rl-row .kp-btn:last-child { border-right: none; }

  /* ── Keypad type visual styles ── */
  .keypad-type-seetouch .kp-btn:not(.raise-lower),
  .keypad-type-seetouch_hybrid .kp-btn:not(.raise-lower) {
    padding-left: 14px; justify-content: flex-start; min-height: 30px;
  }
  .keypad-type-seetouch .kp-btn:not(.raise-lower)::before,
  .keypad-type-seetouch_hybrid .kp-btn:not(.raise-lower)::before {
    content: ''; position: absolute; left: 5px; top: 50%; transform: translateY(-50%);
    width: 5px; height: 5px; border-radius: 50%;
    background: #1a3d2b; border: 1px solid #2d5a38;
  }
  .keypad-type-seetouch .kp-btn.configured:not(.raise-lower)::before,
  .keypad-type-seetouch_hybrid .kp-btn.configured:not(.raise-lower)::before {
    background: #4caf50; border-color: #4caf50; box-shadow: 0 0 4px #4caf50;
  }
  .keypad-type-seetouch .kp-btn.selected:not(.raise-lower)::before,
  .keypad-type-seetouch_hybrid .kp-btn.selected:not(.raise-lower)::before {
    background: #81c784; border-color: #81c784;
  }
  .keypad-type-palladiom .kp-btn:not(.raise-lower) { border-radius: 3px; aspect-ratio: 2/1; min-height: 28px; }
  .keypad-type-palladiom .kp-btn.configured::after { display: none; }
  .keypad-type-palladiom .kp-btn.configured { border-bottom: 2px solid #4caf50; }
  .keypad-type-pico .keypad-device { border-radius: 18px; padding: 10px 10px; background: #1e1e1e; }
  .keypad-type-pico .kp-btn { border-radius: 50%; aspect-ratio: 1; min-height: 32px; width: 32px; max-width: 100%; margin: 0 auto; }
  .keypad-type-pico .kp-col { align-items: center; }
  .keypad-type-tabletop .kp-btn { border-radius: 3px; min-height: 26px; font-size: 8px; }
  .keypad-type-alisee .kp-col { align-items: center; gap: 8px; }
  .kp-btn-alisee-wrap {
    display: flex; flex-direction: column; align-items: center; gap: 4px; cursor: pointer;
  }
  .kp-btn-alisee-wrap .kp-btn {
    border-radius: 50%; aspect-ratio: 1; min-height: 32px; width: 32px;
    max-width: 100%; margin: 0; padding: 0; font-size: 0;
  }
  .kp-btn-engraving {
    font-size: 8px; color: #bdbdbd; text-align: center;
    word-break: break-word; max-width: 44px; line-height: 1.2; pointer-events: none;
  }

  /* ── Entity search ── */
  .tree-search-wrap { padding: 6px 10px 0; }
  .tree-search-wrap input {
    width: 100%; box-sizing: border-box; border: 1px solid var(--divider-color, #ccc);
    border-radius: 4px; padding: 5px 10px; font-size: 12px; background: var(--card-background-color,#fff);
    color: var(--primary-text-color,#212121); outline: none;
  }
  .tree-search-wrap input:focus { border-color: #4caf50; }

  /* ── Modal / Add Keypad dialog ── */
  .modal-overlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.6);
    display: flex; align-items: center; justify-content: center; z-index: 1000;
  }
  .modal-overlay.hidden { display: none; }
  .modal {
    background: var(--card-background-color, #fff); border-radius: 10px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4); width: 480px; max-width: 95vw;
    max-height: 80vh; display: flex; flex-direction: column; overflow: hidden;
  }
  .modal-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 16px 20px; border-bottom: 1px solid var(--divider-color,#eee);
    font-size: 16px; font-weight: 600; color: var(--primary-text-color,#212121);
    flex-shrink: 0;
  }
  .modal-close {
    background: none; border: none; font-size: 18px; cursor: pointer; color: #888; padding: 0 4px;
  }
  .modal-close:hover { color: var(--primary-text-color,#212121); }
  .modal-body { flex: 1; overflow-y: auto; padding: 16px 20px; }
  .modal-loading, .modal-empty { text-align: center; color: var(--secondary-text-color,#757575); padding: 24px 0; }
  .modal-error { color: #e53935; font-size: 13px; margin-top: 10px; }
  .modal-hint { font-size: 13px; color: var(--secondary-text-color,#757575); margin: 0 0 10px; }
  .modal-devices { display: flex; flex-direction: column; gap: 8px; }
  .device-card {
    border: 1px solid var(--divider-color,#eee); border-radius: 8px; padding: 10px 14px;
    cursor: pointer; transition: all 0.15s; display: flex; flex-direction: column; gap: 3px;
  }
  .device-card:hover { border-color: #4caf50; background: rgba(76,175,80,0.05); }
  .device-card.selected { border-color: #4caf50; background: rgba(76,175,80,0.1); box-shadow: 0 0 0 2px rgba(76,175,80,0.3); }
  .device-card-main { display: flex; align-items: baseline; gap: 8px; }
  .device-card-name { font-size: 14px; font-weight: 500; color: var(--primary-text-color,#212121); }
  .device-card-area { font-size: 12px; color: var(--secondary-text-color,#757575); }
  .device-card-meta { display: flex; gap: 8px; }
  .device-card-type {
    font-size: 10px; background: rgba(76,175,80,0.15); color: #2e7d32;
    padding: 1px 6px; border-radius: 3px; text-transform: capitalize;
  }
  .device-card-model { font-size: 10px; color: var(--secondary-text-color,#9e9e9e); font-family: monospace; }
  .modal-add-form { margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--divider-color,#eee); }
  .modal-add-form.hidden { display: none; }
  .modal-add-form label { font-size: 12px; font-weight: 500; color: var(--secondary-text-color,#757575); display: block; margin-bottom: 4px; }
  .modal-add-form input {
    width: 100%; box-sizing: border-box; border: 1px solid var(--divider-color,#ccc);
    border-radius: 4px; padding: 8px 10px; font-size: 14px; outline: none;
    background: var(--card-background-color,#fff); color: var(--primary-text-color,#212121);
  }
  .modal-add-form input:focus { border-color: #4caf50; }
  .modal-form-actions { display: flex; gap: 10px; margin-top: 12px; justify-content: flex-end; }
  .modal-btn-cancel {
    background: none; border: 1px solid var(--divider-color,#ccc); border-radius: 4px;
    padding: 7px 16px; cursor: pointer; font-size: 13px; color: var(--primary-text-color,#212121);
  }
  .modal-btn-cancel:hover { background: rgba(0,0,0,0.05); }
  .modal-btn-confirm {
    background: #2e7d32; color: #fff; border: none; border-radius: 4px;
    padding: 7px 20px; cursor: pointer; font-size: 13px; font-weight: 500;
  }
  .modal-btn-confirm:hover { background: #388e3c; }
  .modal-btn-confirm:disabled { background: #888; cursor: default; }

  /* ── Engraving ── */
  .engraving-section { width: 100%; display: flex; flex-direction: column; gap: 4px; }
  .engraving-section label {
    font-size: 10px; color: var(--secondary-text-color, #757575);
    font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;
  }
  .engraving-section input {
    width: 100%; padding: 5px 7px; border: 1px solid var(--divider-color, #ccc);
    border-radius: 4px; font-size: 12px;
    background: var(--card-background-color, #fff); color: var(--primary-text-color);
    box-sizing: border-box;
  }
  .engraving-section input:focus { outline: none; border-color: #4caf50; box-shadow: 0 0 0 2px rgba(76,175,80,0.15); }

  /* ── Right column ── */
  .col-right { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

  /* ── Config strip ── */
  .btn-config-strip {
    background: var(--card-background-color, #fff); border-bottom: 1px solid var(--divider-color, #e0e0e0);
    padding: 10px 16px; flex-shrink: 0; display: flex; flex-wrap: wrap; align-items: center; gap: 16px;
  }
  .config-field { display: flex; flex-direction: column; gap: 3px; }
  .config-field label {
    font-size: 10px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.6px; color: var(--secondary-text-color, #757575);
  }
  .config-field select, .config-field input[type="text"], .config-field input[type="number"] {
    border: 1px solid var(--divider-color, #ccc); border-radius: 4px; padding: 5px 8px;
    font-size: 13px; background: var(--card-background-color, #fff);
    color: var(--primary-text-color); cursor: pointer; min-width: 120px;
  }
  .config-field select:focus, .config-field input:focus {
    outline: none; border-color: #4caf50; box-shadow: 0 0 0 2px rgba(76,175,80,0.15);
  }
  .checkbox-field {
    display: flex; align-items: center; gap: 6px; padding-top: 14px; font-size: 13px; cursor: pointer;
  }
  .checkbox-field input[type="checkbox"] { accent-color: #2e7d32; width: 15px; height: 15px; }

  /* ── Extra config (stateful_scene fields) ── */
  .extra-config {
    background: var(--secondary-background-color, #f5f5f5);
    border-bottom: 1px solid var(--divider-color, #e0e0e0);
    padding: 8px 16px; display: flex; flex-wrap: wrap; gap: 14px;
    align-items: center; flex-shrink: 0;
  }
  .extra-config.hidden { display: none; }

  /* ── Entity tree ── */
  .tree-section { flex: 1; display: flex; flex-direction: column; overflow: hidden; background: var(--secondary-background-color, #f5f5f5); }
  .tree-filter-bar {
    background: var(--card-background-color, #fff); border-bottom: 1px solid var(--divider-color, #e0e0e0);
    padding: 8px 16px; display: flex; flex-wrap: wrap; align-items: center; gap: 10px; flex-shrink: 0; font-size: 12px;
  }
  .tree-filter-bar label { color: var(--secondary-text-color, #757575); font-weight: 500; }
  .tree-filter-bar select {
    border: 1px solid var(--divider-color, #ccc); border-radius: 4px; padding: 4px 8px;
    font-size: 12px; background: var(--card-background-color, #fff); color: var(--primary-text-color); cursor: pointer;
  }
  .tree-filter-bar select:focus { outline: none; border-color: #4caf50; }
  .tree-filter-bar .expand-all {
    margin-left: auto; background: none; border: none; color: #4caf50;
    cursor: pointer; font-size: 12px; text-decoration: underline;
  }
  .tree-container { flex: 1; overflow-y: auto; padding: 4px 0; }
  .tree-empty { padding: 32px 16px; text-align: center; color: var(--secondary-text-color, #757575); font-size: 13px; }
  .area-node { border-bottom: 1px solid var(--divider-color, #ebebeb); }
  .area-header {
    display: flex; align-items: center; padding: 7px 16px; cursor: pointer;
    background: var(--card-background-color, #fff); user-select: none; transition: background 0.12s; gap: 8px;
  }
  .area-header:hover { background: rgba(76,175,80,0.06); }
  .area-expand { font-size: 10px; color: var(--secondary-text-color, #aaa); width: 14px; }
  .area-check { accent-color: #2e7d32; width: 14px; height: 14px; cursor: pointer; }
  .area-name { font-weight: 600; font-size: 13px; flex: 1; }
  .area-count { font-size: 11px; color: var(--secondary-text-color, #757575); }
  .area-entities { display: none; background: var(--secondary-background-color, #fafafa); }
  .area-entities.open { display: block; }
  .entity-row {
    display: flex; align-items: center; padding: 5px 16px 5px 38px; gap: 8px;
    cursor: pointer; transition: background 0.1s; border-top: 1px solid var(--divider-color, #f0f0f0);
  }
  .entity-row:hover { background: rgba(76,175,80,0.06); }
  .entity-row.selected { background: rgba(76,175,80,0.12); }
  .entity-check { accent-color: #2e7d32; width: 14px; height: 14px; cursor: pointer; flex-shrink: 0; }
  .entity-icon { font-size: 14px; width: 20px; text-align: center; flex-shrink: 0; }
  .entity-name { flex: 1; font-size: 13px; }
  .entity-state { font-size: 11px; color: var(--secondary-text-color, #757575); text-align: right; min-width: 50px; }
  .entity-state.on { color: #4caf50; font-weight: 500; }

  /* ── Programming summary (bottom) ── */
  .summary-section {
    background: var(--card-background-color, #fff);
    flex-shrink: 0; min-height: 60px; overflow-y: auto;
  }
  .summary-header {
    padding: 6px 16px; background: var(--secondary-background-color, #f5f5f5);
    font-size: 11px; font-weight: 600; letter-spacing: 0.6px; text-transform: uppercase;
    color: var(--secondary-text-color, #757575); border-bottom: 1px solid var(--divider-color, #e0e0e0);
    display: flex; justify-content: space-between; align-items: center;
    position: sticky; top: 0; z-index: 1;
  }
  .summary-table { width: 100%; border-collapse: collapse; font-size: 12px; }
  .summary-table th {
    text-align: left; padding: 5px 10px;
    background: var(--secondary-background-color, #f5f5f5);
    border-bottom: 1px solid var(--divider-color, #e0e0e0);
    font-weight: 600; color: var(--secondary-text-color, #757575);
    font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px;
    position: sticky; top: 37px; white-space: nowrap;
  }
  .summary-table td { padding: 5px 10px; border-bottom: 1px solid var(--divider-color, #f0f0f0); vertical-align: middle; }
  .summary-table tr:hover td { background: rgba(76,175,80,0.06); }
  .summary-empty { padding: 12px 16px; font-size: 12px; color: var(--secondary-text-color, #bbb); font-style: italic; }
  .type-badge {
    display: inline-block; padding: 1px 5px; border-radius: 3px; font-size: 10px;
    background: rgba(76,175,80,0.15); color: #4caf50; font-weight: 600; white-space: nowrap;
  }
  .remove-entity { background: none; border: none; color: #ef5350; cursor: pointer; font-size: 14px; padding: 0 4px; opacity: 0.6; }
  .remove-entity:hover { opacity: 1; }

  /* ── Per-entity setting inputs in summary table ── */
  .ent-setting {
    width: 64px; padding: 3px 5px;
    border: 1px solid var(--divider-color, #ccc); border-radius: 3px;
    font-size: 11px; background: var(--card-background-color, #fff);
    color: var(--primary-text-color); text-align: right;
  }
  .ent-setting:focus { outline: none; border-color: #4caf50; }
  .ent-setting:placeholder-shown { color: var(--secondary-text-color, #aaa); }
  .ent-color-input {
    width: 34px; height: 22px; padding: 1px; border: 1px solid var(--divider-color, #ccc);
    border-radius: 3px; cursor: pointer; background: none;
  }
  .no-cap { color: var(--secondary-text-color, #aaa); font-size: 12px; }
  .cap-hint { font-size: 10px; color: var(--secondary-text-color, #aaa); font-style: italic; }
  .state-on { color: #4caf50; font-weight: 500; }

  /* ── Tab bar (Press On / Off Level / Double Tap / Hold) ── */
  .tab-bar {
    display: flex; align-items: stretch; border-bottom: 2px solid var(--divider-color, #e0e0e0);
    background: var(--card-background-color, #fff); flex-shrink: 0;
  }
  .tab-btn {
    padding: 8px 16px; font-size: 12px; font-weight: 500; cursor: pointer;
    border: none; background: none; color: var(--secondary-text-color, #757575);
    border-bottom: 2px solid transparent; margin-bottom: -2px;
    transition: color 0.15s, border-color 0.15s; white-space: nowrap;
  }
  .tab-btn:hover { color: #2e7d32; }
  .tab-btn.active { color: #2e7d32; border-bottom-color: #4caf50; font-weight: 600; }
  .tab-btn:disabled { opacity: 0.35; cursor: default; }

  /* ── Off Level tab ── */
  .off-level-section {
    flex: 1; overflow-y: auto; padding: 12px 16px;
    background: var(--secondary-background-color, #f5f5f5);
  }
  .off-level-hint {
    font-size: 12px; color: var(--secondary-text-color, #757575); margin-bottom: 12px;
    padding: 8px 12px; background: rgba(76,175,80,0.06); border-radius: 4px;
    border-left: 3px solid #a5d6a7;
  }
  .off-level-table { width: 100%; border-collapse: collapse; font-size: 12px; }
  .off-level-table th {
    text-align: left; padding: 5px 10px;
    background: var(--card-background-color, #fff);
    border-bottom: 1px solid var(--divider-color, #e0e0e0);
    font-weight: 600; color: var(--secondary-text-color, #757575);
    font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px;
  }
  .off-level-table td { padding: 6px 10px; border-bottom: 1px solid var(--divider-color, #f0f0f0); vertical-align: middle; }

  /* ── Sub-action config (double_tap / hold tabs) ── */
  .sub-action-section {
    flex: 1; display: flex; flex-direction: column; overflow: hidden;
  }
  .sub-action-strip {
    background: var(--card-background-color, #fff);
    border-bottom: 1px solid var(--divider-color, #e0e0e0);
    padding: 10px 16px; flex-shrink: 0; display: flex; flex-wrap: wrap; align-items: center; gap: 16px;
  }
  .sub-action-hint {
    font-size: 12px; color: var(--secondary-text-color, #9e9e9e); padding: 8px 0;
  }
`;

// ── Tab definitions ───────────────────────────────────────────────
const TABS = [
  { id: "press_on",   label: "Press On" },
  { id: "off_level",  label: "Off Level" },
  { id: "double_tap", label: "Double Tap" },
  { id: "hold",       label: "Hold" },
];

// ── Helpers ───────────────────────────────────────────────────────

function getLightCaps(hass, entityId) {
  if (!entityId.startsWith("light.")) return null;
  const st = hass.states?.[entityId];
  if (!st) return { brightness: true, colorTemp: false, color: false };
  const modes = st.attributes?.supported_color_modes || [];
  const feats = st.attributes?.supported_features || 0;
  return {
    brightness: modes.some(m => m !== "onoff") || !!(feats & 1),
    colorTemp:  modes.includes("color_temp") || !!(feats & 2),
    color:      modes.some(m => ["hs","rgb","xy","rgbw","rgbww"].includes(m)) || !!(feats & 16),
  };
}

function hsToHex(h, s) {
  const sv = s / 100;
  const hi = Math.floor(h / 60) % 6;
  const f  = h / 60 - Math.floor(h / 60);
  const p  = 1 - sv;
  const q  = 1 - f * sv;
  const t  = 1 - (1 - f) * sv;
  const [r, g, b] = [[1,t,p],[q,1,p],[p,1,t],[p,q,1],[t,p,1],[1,p,q]][hi];
  const hex = v => Math.round(v * 255).toString(16).padStart(2, "0");
  return `#${hex(r)}${hex(g)}${hex(b)}`;
}

function hexToHs(hex) {
  const r = parseInt(hex.slice(1,3), 16) / 255;
  const g = parseInt(hex.slice(3,5), 16) / 255;
  const b = parseInt(hex.slice(5,7), 16) / 255;
  const max = Math.max(r,g,b), min = Math.min(r,g,b), d = max - min;
  const s = max === 0 ? 0 : d / max;
  let h = 0;
  if (d !== 0) {
    if (max === r) h = ((g - b) / d) % 6;
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h = h * 60;
    if (h < 0) h += 360;
  }
  return [Math.round(h), Math.round(s * 100)];
}

function entityIcon(entityId, state) {
  const domain = entityId.split(".")[0];
  const isOn = state && !["off","closed","unavailable","unknown"].includes(state);
  const icons = {
    light: isOn ? "💡" : "🔦", switch: isOn ? "🔵" : "⚪", scene: "🎬",
    automation: "⚙️", script: "📜", cover: state === "open" ? "🪟" : "🔲",
    fan: isOn ? "🌀" : "💨", media_player: "📺", input_boolean: isOn ? "✅" : "⭕",
  };
  return icons[domain] || "▪️";
}

function entityStateLabel(entityId, state, attributes) {
  if (!state) return "";
  const domain = entityId.split(".")[0];
  if (domain === "light" && state === "on") {
    const bri = attributes?.brightness;
    if (bri != null) return Math.round(bri / 255 * 100) + "%";
    return "On";
  }
  if (domain === "cover") return state.charAt(0).toUpperCase() + state.slice(1);
  if (state === "unavailable") return "N/A";
  return state.charAt(0).toUpperCase() + state.slice(1);
}

function friendlyName(hass, entityId, entityEntry) {
  if (entityEntry?.name) return entityEntry.name;
  const state = hass.states?.[entityId];
  if (state?.attributes?.friendly_name) return state.attributes.friendly_name;
  return entityId.split(".")[1].replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

function resolveAreaId(entityId, hass) {
  const ent = hass.entities?.[entityId];
  if (!ent) return null;
  if (ent.area_id) return ent.area_id;
  if (ent.device_id) {
    const dev = hass.devices?.[ent.device_id];
    if (dev?.area_id) return dev.area_id;
  }
  return null;
}

function areaName(hass, areaId) {
  if (!areaId) return "No Area";
  return hass.areas?.[areaId]?.name || areaId;
}

function getLayout(keypadType) {
  return KEYPAD_LAYOUTS[keypadType] || KEYPAD_LAYOUTS.generic;
}

function getButtonsFromEntry(entryData) {
  const btnNums = entryData.button_numbers;
  if (btnNums && btnNums.length > 0) {
    const raise = entryData.raise_button;
    const lower = entryData.lower_button;
    return btnNums.map(n => ({ number: n, is_raise: n === raise, is_lower: n === lower }));
  }
  const kt = entryData.keypad_type || "generic";
  const layout = getLayout(kt);
  const buttons = [];
  for (let i = 1; i <= layout.mainCount; i++) {
    buttons.push({ number: i, is_raise: false, is_lower: false });
  }
  if (layout.hasRL) {
    buttons.push({ number: layout.mainCount + 1, is_raise: true, is_lower: false });
    buttons.push({ number: layout.mainCount + 2, is_raise: false, is_lower: true });
  }
  return buttons;
}

function defaultBtnCfg() {
  return {
    // Top-level (global) fields
    label: "", led_entity: "", led_invert: false, led_mode: "room",
    scene_group: "", cycle_dim: false, enabled: true,
    // Press On fields (at top level for backward compat with v1 backend)
    action_type: "none", action_target: "", entity_settings: {},
    target_brightness: 0, target_color_temp: 0,
    // v2 sub-blocks
    off_level:  { entity_settings: {} },
    double_tap: { action_type: "none", action_target: "", entity_settings: {} },
    hold:       { action_type: "none", action_target: "", entity_settings: {} },
  };
}

function migrateToV2(saved) {
  // Ensure v2 sub-block keys exist on a saved config (v1 has none of these)
  const def = defaultBtnCfg();
  return {
    ...def,
    ...saved,
    off_level:  saved.off_level  || def.off_level,
    double_tap: saved.double_tap ? { ...def.double_tap, ...saved.double_tap } : def.double_tap,
    hold:       saved.hold       ? { ...def.hold,       ...saved.hold       } : def.hold,
    entity_settings: saved.entity_settings || {},
  };
}

// ── Panel web component ───────────────────────────────────────────

class LutronKeypadsPanel extends HTMLElement {

  constructor() {
    super();
    this._hass = null;
    this._entries = [];
    this._selectedEntryId = null;
    this._selectedButton = 1;
    this._pendingConfig = {};
    this._dirty = {};
    this._expandedAreas = new Set();
    this._filterArea = "";
    this._sidebarSearch = "";
    this._entitySearch = "";
    this._selectedDiscoveryDevice = null;
    this._activeTabs = {};  // entryId → btnNum → tab id ("press_on"|"off_level"|"double_tap"|"hold")
    this._initialized = false;
    this._shadow = this.attachShadow({ mode: "open" });

    // Resizable panel sizes (px)
    this._sidebarWidth = 220;
    this._keypayWidth = 186;
    this._summaryHeight = 220;
    this._sidebarResizerBound = false;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._initialized) { this._initialized = true; this._setup(); }
  }

  set panel(panel) { this._panel = panel; }

  connectedCallback() {
    if (this._hass && !this._initialized) { this._initialized = true; this._setup(); }
  }

  async _setup() {
    this._injectStyles();
    this._buildSkeleton();
    await this._loadEntries();

    const params = new URLSearchParams(window.location.search);
    const paramEntry = params.get("entry");
    if (paramEntry && this._entries.find(e => e.entry_id === paramEntry)) {
      this._selectEntry(paramEntry);
    } else if (this._entries.length === 1) {
      this._selectEntry(this._entries[0].entry_id);
    }

    this._renderSidebar();
    this._renderMain();
  }

  _injectStyles() {
    const style = document.createElement("style");
    style.textContent = STYLES;
    this._shadow.appendChild(style);
  }

  _buildSkeleton() {
    const root = document.createElement("div");
    root.className = "panel-body";
    root.innerHTML = `
      <div class="sidebar" id="sidebar" style="width:${this._sidebarWidth}px">
        <div class="sidebar-header">
          <span>Lutron Keypads</span>
          <button class="btn-add-keypad" id="btn-add-keypad" title="Add Keypad">+</button>
        </div>
        <div class="sidebar-search-wrap">
          <input type="search" id="sidebar-search" placeholder="Search keypads…">
        </div>
        <div class="sidebar-list" id="sidebar-list"></div>
      </div>
      <div class="resize-handle-v" id="sidebar-resizer"></div>
      <div class="main" id="main-content">
        <div class="welcome">
          <div class="welcome-icon">⌨️</div>
          <h2>Lutron Keypad Programming</h2>
          <p>Select a keypad from the left to begin programming</p>
        </div>
      </div>
    `;

    const modal = document.createElement("div");
    modal.className = "modal-overlay hidden";
    modal.id = "modal-overlay";
    modal.innerHTML = `
      <div class="modal">
        <div class="modal-header">
          <span>Add Keypad</span>
          <button class="modal-close" id="modal-close">✕</button>
        </div>
        <div class="modal-body" id="modal-body">
          <div class="modal-loading">Discovering keypads…</div>
        </div>
      </div>
    `;

    const header = document.createElement("div");
    header.className = "panel-header";
    header.innerHTML = `
      <span class="logo">Lutron</span>
      <span class="subtitle" id="header-subtitle">Keypad Programming</span>
      <span class="save-status" id="save-status"></span>
      <button class="btn-save" id="btn-save" disabled>Save Changes</button>
    `;

    this._shadow.appendChild(header);
    this._shadow.appendChild(root);
    this._shadow.appendChild(modal);

    this._shadow.getElementById("btn-save").addEventListener("click", () => this._saveConfig());

    this._shadow.getElementById("sidebar-search").addEventListener("input", e => {
      this._sidebarSearch = e.target.value;
      this._renderSidebar();
    });

    this._shadow.getElementById("btn-add-keypad").addEventListener("click", () => this._showAddDialog());

    this._shadow.getElementById("modal-close").addEventListener("click", () => this._closeDialog());
    modal.addEventListener("click", e => { if (e.target === modal) this._closeDialog(); });

    this._initResizers();
  }

  async _loadEntries() {
    try {
      this._entries = await this._hass.callWS({ type: "lutron_keypad_controller/get_entries" });
    } catch (e) {
      console.error("LutronPanel: failed to load entries", e);
      this._entries = [];
    }
  }

  // ── Sidebar ────────────────────────────────────────────────────

  _renderSidebar() {
    const list = this._shadow.getElementById("sidebar-list");
    if (!list) return;

    if (this._entries.length === 0) {
      list.innerHTML = `<div style="padding:14px;color:#81c784;font-size:12px;">No keypads configured.<br>Click <b>+</b> above to add one.</div>`;
      return;
    }

    const q = (this._sidebarSearch || "").toLowerCase().trim();
    const filtered = q
      ? this._entries.filter(e => {
          const name  = (e.title || "").toLowerCase();
          const area  = (e.data?.area_name || "").toLowerCase();
          const ktype = (e.data?.keypad_type || "").toLowerCase();
          return name.includes(q) || area.includes(q) || ktype.includes(q);
        })
      : this._entries;

    if (filtered.length === 0) {
      list.innerHTML = `<div style="padding:14px;color:#81c784;font-size:12px;">No keypads match "${this._esc(this._sidebarSearch)}".</div>`;
      return;
    }

    const byArea = {};
    for (const entry of filtered) {
      const area = entry.data?.area_name || "";
      if (!byArea[area]) byArea[area] = [];
      byArea[area].push(entry);
    }

    let html = "";
    for (const [area, entries] of Object.entries(byArea)) {
      if (area) html += `<div class="sidebar-area">${area}</div>`;
      for (const entry of entries) {
        const active = entry.entry_id === this._selectedEntryId ? "active" : "";
        const ktype = (entry.data?.keypad_type || "generic").replace(/_/g, " ");
        const model = entry.data?.model_number || "";
        html += `
          <div class="sidebar-entry ${active}" data-entry="${entry.entry_id}">
            <span class="entry-name">${entry.title}</span>
            <div style="display:flex;align-items:center;gap:5px;flex-wrap:wrap">
              <span class="entry-type">${ktype}</span>
              ${model ? `<span class="entry-model">${this._esc(model)}</span>` : ""}
            </div>
          </div>`;
      }
    }
    list.innerHTML = html;

    list.querySelectorAll(".sidebar-entry").forEach(el => {
      el.addEventListener("click", () => {
        this._selectEntry(el.dataset.entry);
        this._renderSidebar();
        this._renderMain();
      });
    });
  }

  _selectEntry(entryId) {
    this._selectedEntryId = entryId;
    const entry = this._getEntry(entryId);
    if (!entry) return;

    if (!this._pendingConfig[entryId]) this._loadPendingFromEntry(entryId, entry);

    const buttons = getButtonsFromEntry(entry.data);
    const firstConfigurable = buttons.find(b => !b.is_raise && !b.is_lower);
    this._selectedButton = firstConfigurable?.number || buttons[0]?.number || 1;

    const subtitle = this._shadow.getElementById("header-subtitle");
    if (subtitle) {
      subtitle.textContent = `${entry.data?.area_name ? entry.data.area_name + " › " : ""}${entry.title}`;
    }
  }

  _loadPendingFromEntry(entryId, entry) {
    const savedButtons = entry.options?.buttons || {};
    const all = getButtonsFromEntry(entry.data);
    const pending = {};
    const names = entry.data?.button_names || {};
    for (const btn of all) {
      const saved = savedButtons[String(btn.number)] || {};
      const migrated = migrateToV2(saved);
      pending[btn.number] = {
        ...migrated,
        label: migrated.label || names[String(btn.number)] || "",
      };
      if (btn.is_raise) { pending[btn.number].action_type = "raise";  pending[btn.number].label = pending[btn.number].label || "Raise"; }
      if (btn.is_lower) { pending[btn.number].action_type = "lower";  pending[btn.number].label = pending[btn.number].label || "Lower"; }
    }
    this._pendingConfig[entryId] = pending;
  }

  _getActiveTab() {
    const tabs = this._activeTabs[this._selectedEntryId];
    return (tabs && tabs[this._selectedButton]) || "press_on";
  }

  _setActiveTab(tab) {
    if (!this._activeTabs[this._selectedEntryId])
      this._activeTabs[this._selectedEntryId] = {};
    this._activeTabs[this._selectedEntryId][this._selectedButton] = tab;
  }

  // ── Main area ──────────────────────────────────────────────────

  _renderMain() {
    const main = this._shadow.getElementById("main-content");
    if (!main) return;
    if (!this._selectedEntryId) {
      main.innerHTML = `
        <div class="welcome">
          <div class="welcome-icon">⌨️</div>
          <h2>Lutron Keypad Programming</h2>
          <p>Select a keypad from the left to begin programming</p>
        </div>`;
      return;
    }

    const entry = this._getEntry(this._selectedEntryId);
    if (!entry) return;

    const buttons = getButtonsFromEntry(entry.data);
    const btn = buttons.find(b => b.number === this._selectedButton);
    const isRL = btn?.is_raise || btn?.is_lower;
    const pending = this._pendingConfig[this._selectedEntryId] || {};
    const btnCfg = pending[this._selectedButton] || defaultBtnCfg();

    const activeTab = this._getActiveTab();

    main.innerHTML = `
      <div class="breadcrumb">
        ${entry.data?.area_name ? `<span>${entry.data.area_name}</span> ›` : ""}
        <span>${entry.title}</span>
      </div>
      <div class="prog-body" id="prog-body">
        ${this._renderKeypadColumn(entry, buttons, btnCfg)}
        <div class="resize-handle-v" id="keypad-resizer"></div>
        <div class="col-right" id="col-right">
          ${this._renderConfigStrip(entry, btnCfg, isRL)}
          ${this._renderExtraConfig(btnCfg, isRL)}
          ${this._renderTabBar(btnCfg, isRL, activeTab)}
          ${this._renderTabContent(entry, btnCfg, isRL, activeTab)}
        </div>
      </div>
      <div class="resize-handle-h" id="summary-resizer"></div>
      ${this._renderSummarySection(entry, btnCfg, isRL, activeTab)}
    `;

    this._attachMainListeners(entry, buttons, btnCfg);
  }

  // ── Keypad visual ──────────────────────────────────────────────

  _renderKeypadColumn(entry, buttons, btnCfg) {
    const ktype = entry.data?.keypad_type || "generic";
    const layout = getLayout(ktype);
    const pending = this._pendingConfig[this._selectedEntryId] || {};
    const names = entry.data?.button_names || {};
    const modelNum = entry.data?.model_number || "";

    const mainButtons = buttons.filter(b => !b.is_raise && !b.is_lower);
    const raiseBtn = buttons.find(b => b.is_raise);
    const lowerBtn = buttons.find(b => b.is_lower);

    // Determine physical column distribution from model number, or fall back to layout.cols
    let colCounts = parsePhysicalColumns(modelNum, ktype);
    if (!colCounts) {
      const numCols = layout.cols || 1;
      const perCol = Math.ceil(mainButtons.length / numCols);
      colCounts = [];
      let rem = mainButtons.length;
      for (let i = 0; i < numCols && rem > 0; i++) {
        const c = Math.min(perCol, rem);
        colCounts.push(c);
        rem -= c;
      }
    }

    const makeBtnDiv = b => {
      const cfg = pending[b.number] || {};
      const label = cfg.label || names[String(b.number)] || `Btn ${b.number}`;
      const sel  = b.number === this._selectedButton ? "selected" : "";
      const conf = cfg.action_type && cfg.action_type !== "none" ? "configured" : "";
      if (ktype === "alisee") {
        return `<div class="kp-btn-alisee-wrap" data-kp-btn="${b.number}">
          <div class="kp-btn ${sel} ${conf}" style="position:relative"></div>
          <span class="kp-btn-engraving">${this._esc(label)}</span>
        </div>`;
      }
      return `<div class="kp-btn ${sel} ${conf}" data-kp-btn="${b.number}" style="position:relative">${this._esc(label)}</div>`;
    };

    // Distribute main buttons across physical columns (top-to-bottom per column)
    let btnIdx = 0;
    const colsHtml = colCounts.map((count, ci) => {
      const isLast = ci === colCounts.length - 1;
      const slice = isLast ? mainButtons.slice(btnIdx) : mainButtons.slice(btnIdx, btnIdx + count);
      btnIdx += count;
      return `<div class="kp-col">${slice.map(makeBtnDiv).join("")}</div>`;
    }).join("");

    let rlHtml = "";
    if (raiseBtn || lowerBtn) {
      rlHtml = `<div class="kp-rl-row">`;
      if (raiseBtn) {
        const sel = raiseBtn.number === this._selectedButton ? "selected" : "";
        rlHtml += `<div class="kp-btn raise-lower ${sel}" data-kp-btn="${raiseBtn.number}" title="Raise">▲</div>`;
      }
      if (lowerBtn) {
        const sel = lowerBtn.number === this._selectedButton ? "selected" : "";
        rlHtml += `<div class="kp-btn raise-lower ${sel}" data-kp-btn="${lowerBtn.number}" title="Lower">▼</div>`;
      }
      rlHtml += `</div>`;
    }

    const allNums = buttons.map(b => b.number);
    const curIdx = allNums.indexOf(this._selectedButton);
    const prevDisabled = curIdx <= 0 ? "disabled" : "";
    const nextDisabled = curIdx >= allNums.length - 1 ? "disabled" : "";
    const prevNum = curIdx > 0 ? allNums[curIdx - 1] : null;
    const nextNum = curIdx < allNums.length - 1 ? allNums[curIdx + 1] : null;
    const label1 = (this._pendingConfig[this._selectedEntryId] || {})[this._selectedButton]?.label || "";

    return `
      <div class="col-keypad" style="width:${this._keypayWidth}px">
        <div class="kp-nav">
          <button id="btn-prev" ${prevDisabled} data-prev="${prevNum}">◀</button>
          <span class="btn-num">Button ${this._selectedButton}</span>
          <button id="btn-next" ${nextDisabled} data-next="${nextNum}">▶</button>
        </div>
        <div class="keypad-device keypad-type-${ktype}">
          <div class="kp-logo">LUTRON</div>
          <div class="kp-main-buttons">${colsHtml}</div>
          ${rlHtml}
        </div>
        <div class="engraving-section">
          <label>Button Label (Engraving)</label>
          <input id="inp-label" type="text" placeholder="Line 1" maxlength="20" value="${this._esc(label1)}">
        </div>
      </div>`;
  }

  // ── Config strip ───────────────────────────────────────────────

  _renderConfigStrip(entry, btnCfg, isRL) {
    const at = btnCfg.action_type || "none";
    const ledMode = btnCfg.led_mode || "room";
    const cycleDim = btnCfg.cycle_dim ? "checked" : "";

    // Cycle Dim checkbox only applies to actions that have assigned light entities
    const CYCLE_DIM_ACTIONS = new Set(["entity_toggle", "light_cycle_dim", "stateful_scene"]);
    const showCycleDim = !isRL && CYCLE_DIM_ACTIONS.has(at);
    const cycleDimForced = at === "light_cycle_dim";
    const cycleDimChecked = cycleDimForced ? "checked" : cycleDim;
    const cycleDimDisabled = cycleDimForced ? "disabled" : (isRL ? "disabled" : "");
    const cycleDimTitle = cycleDimForced
      ? 'title="Dim Cycle always uses tap-to-step / hold-to-ramp"'
      : 'title="Hold to dim continuously; tap for normal action"';

    const ledOptions = Object.entries(LED_LOGIC).map(([val, label]) =>
      `<option value="${val}" ${val === ledMode ? "selected" : ""}>${label}</option>`
    ).join("");

    return `
      <div class="btn-config-strip">
        <div class="config-field">
          <label>LED Logic</label>
          <select id="sel-led-logic" ${isRL ? "disabled" : ""}>${ledOptions}</select>
        </div>
        ${showCycleDim ? `
        <label class="checkbox-field" ${cycleDimTitle}>
          <input id="chk-cycle-dim" type="checkbox" ${cycleDimChecked} ${cycleDimDisabled}>
          Hold to Dim
        </label>` : ""}
        <label class="checkbox-field">
          <input id="chk-led-invert" type="checkbox" ${btnCfg.led_invert ? "checked" : ""} ${isRL ? "disabled" : ""}>
          Invert LED
        </label>
      </div>`;
  }

  // ── Tab bar ────────────────────────────────────────────────────

  _renderTabBar(btnCfg, isRL, activeTab) {
    if (isRL) return "";
    const cycleDim = btnCfg.cycle_dim || false;
    const at = btnCfg.action_type || "none";
    const hasEntities = (ACTION_TYPES[at]?.domains || []).length > 0;
    const showOffLevel = at === "entity_toggle";

    return `<div class="tab-bar">
      ${TABS.map(t => {
        let disabled = "";
        if (t.id === "off_level"  && !showOffLevel)     disabled = "disabled";
        if (t.id === "hold"       && cycleDim)           disabled = "disabled title='Disabled when Hold to Dim is active'";
        const active = t.id === activeTab ? "active" : "";
        return `<button class="tab-btn ${active}" data-tab="${t.id}" ${disabled}>${t.label}</button>`;
      }).join("")}
    </div>`;
  }

  // ── Tab content routing ────────────────────────────────────────

  _renderTabContent(entry, btnCfg, isRL, activeTab) {
    if (isRL) {
      return `<div class="tree-section"><div class="tree-empty">Raise/Lower buttons use the last active button's context — no direct assignment needed.</div></div>`;
    }
    if (activeTab === "off_level") return this._renderOffLevelTab(entry, btnCfg);
    if (activeTab === "double_tap") return this._renderSubActionTab(entry, btnCfg, "double_tap");
    if (activeTab === "hold")       return this._renderSubActionTab(entry, btnCfg, "hold");
    // Default: press_on
    return this._renderPressOnTab(entry, btnCfg);
  }

  _renderPressOnTab(entry, btnCfg) {
    const at = btnCfg.action_type || "none";
    const atOptions = Object.entries(ACTION_TYPES).map(([val, info]) =>
      `<option value="${val}" ${val === at ? "selected" : ""}>${info.label}</option>`
    ).join("");
    const actionStrip = `
      <div class="btn-config-strip" style="border-bottom:none;padding-bottom:6px">
        <div class="config-field">
          <label>Action Type</label>
          <select id="sel-action-type">${atOptions}</select>
        </div>
      </div>`;
    return actionStrip + this._renderTreeSection(entry, btnCfg, false);
  }

  _renderOffLevelTab(entry, btnCfg) {
    const targets = this._getSelectedTargets(btnCfg).filter(eid => eid.startsWith("light."));
    if (targets.length === 0) {
      return `<div class="off-level-section"><div class="off-level-hint">Add lights to Press On first. Off Level sets a non-zero dim level used when turning lights off — useful for "dim to 10%" instead of fully off.</div></div>`;
    }
    const offLevelSettings = btnCfg.off_level?.entity_settings || {};
    const rows = targets.map(eid => {
      const entEntry = this._hass.entities?.[eid];
      const name = friendlyName(this._hass, eid, entEntry);
      const val = offLevelSettings[eid]?.brightness > 0 ? offLevelSettings[eid].brightness : "";
      return `<tr>
        <td style="font-size:12px">${this._esc(name)}<div style="font-size:10px;color:var(--secondary-text-color,#9e9e9e)">${this._esc(eid)}</div></td>
        <td><input class="ent-setting ol-setting" type="number" min="1" max="100"
             data-entity="${eid}" data-key="brightness"
             value="${val}" placeholder="off" title="Dim to this % when turning off (blank = full off)"></td>
      </tr>`;
    }).join("");
    return `
      <div class="off-level-section">
        <div class="off-level-hint">
          Set a dim level (1–100%) to use when turning off each light. Leave blank to turn fully off.
        </div>
        <table class="off-level-table">
          <thead><tr><th>Light</th><th>Off Level&nbsp;%</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
  }

  _renderSubActionTab(entry, btnCfg, tabName) {
    const tabCfg  = btnCfg[tabName] || {};
    const at = tabCfg.action_type || "none";
    const cycleDim = btnCfg.cycle_dim || false;
    const isHold = tabName === "hold";
    const disabled = isHold && cycleDim ? "disabled" : "";

    const atOptions = Object.entries(ACTION_TYPES).map(([val, info]) =>
      `<option value="${val}" ${val === at ? "selected" : ""}>${info.label}</option>`
    ).join("");

    const info = ACTION_TYPES[at];
    const domains = info?.domains || [];
    const esq = (this._entitySearch || "").toLowerCase().trim();
    const allEntities = this._getEntitiesForAction(at);
    const entities = esq
      ? allEntities.filter(e => e.name.toLowerCase().includes(esq) || e.entity_id.toLowerCase().includes(esq))
      : allEntities;
    const byArea = this._groupByArea(entities);
    const areaKeys = Object.keys(byArea).sort((a, b) => {
      if (a === "_none") return 1; if (b === "_none") return -1;
      return areaName(this._hass, a).localeCompare(areaName(this._hass, b));
    });

    const isMulti = info?.multi || false;
    const selectedTargets = this._getSelectedTargets(tabCfg);

    let treeHtml = "";
    if (domains.length > 0) {
      for (const areaId of areaKeys) {
        if (this._filterArea && areaId !== this._filterArea && areaId !== "_none") continue;
        const areaEntities = byArea[areaId];
        const expanded = this._expandedAreas.has(areaId);
        const selCount = areaEntities.filter(e => selectedTargets.includes(e.entity_id)).length;
        const allSel = selCount === areaEntities.length && areaEntities.length > 0;
        const someSel = selCount > 0 && !allSel;
        const label = areaId === "_none" ? "No Area" : areaName(this._hass, areaId);
        treeHtml += `
          <div class="area-node">
            <div class="area-header" data-area-toggle="${areaId}">
              <span class="area-expand">${expanded ? "▼" : "▶"}</span>
              <input type="checkbox" class="area-check sub-area-check" data-area-check="${areaId}" data-tab="${tabName}"
                     ${allSel ? "checked" : ""} ${someSel ? "data-indeterminate" : ""}>
              <span class="area-name">${this._esc(label)}</span>
              <span class="area-count">${selCount > 0 ? selCount + " of " : ""}${areaEntities.length} ${selCount > 0 ? "selected" : "available"}</span>
            </div>
            <div class="area-entities ${expanded ? "open" : ""}" id="area-ents-${areaId}">
              ${areaEntities.map(ent => this._renderSubEntityRow(ent, selectedTargets, isMulti, tabName)).join("")}
            </div>
          </div>`;
      }
      if (!treeHtml) treeHtml = `<div class="tree-empty">No entities found.</div>`;
    } else {
      treeHtml = `<div class="tree-empty">${
        at === "none" ? "Select an action type above." : "This action type needs no entity."
      }</div>`;
    }

    const hintText = isHold && cycleDim
      ? `<div class="sub-action-hint">Hold to Dim is active — Hold action is disabled. Uncheck "Hold to Dim" to configure a custom hold action.</div>`
      : "";

    return `
      <div class="sub-action-section">
        <div class="sub-action-strip">
          <div class="config-field">
            <label>Action Type</label>
            <select id="sel-sub-action-${tabName}" data-tab="${tabName}" ${disabled}>${atOptions}</select>
          </div>
          ${hintText}
        </div>
        <div class="tree-section" style="flex:1">
          <div class="tree-container">${treeHtml}</div>
        </div>
      </div>`;
  }

  _renderSubEntityRow(ent, selectedTargets, isMulti, tabName) {
    const sel = selectedTargets.includes(ent.entity_id);
    const stateVal = this._hass.states?.[ent.entity_id]?.state;
    const attrs = this._hass.states?.[ent.entity_id]?.attributes || {};
    const stateLabel = entityStateLabel(ent.entity_id, stateVal, attrs);
    const icon = entityIcon(ent.entity_id, stateVal);
    const isOn = stateVal && !["off","closed","unavailable","unknown"].includes(stateVal);
    const inputType = isMulti ? "checkbox" : "radio";
    return `
      <div class="entity-row ${sel ? "selected" : ""}" data-entity="${ent.entity_id}">
        <input type="${inputType}" class="entity-check sub-entity-check" ${sel ? "checked" : ""}
               data-entity-check="${ent.entity_id}" data-tab="${tabName}">
        <span class="entity-icon">${icon}</span>
        <span class="entity-name">${this._esc(ent.name)}</span>
        <span class="entity-state ${isOn ? "on" : ""}">${stateLabel}</span>
      </div>`;
  }

  // ── Extra config (stateful_scene: scene group + LED override) ──

  _renderExtraConfig(btnCfg, isRL) {
    const at = btnCfg.action_type || "none";
    const showSg  = !isRL && at === "stateful_scene";
    const showLed = !isRL && at === "stateful_scene";

    if (isRL || (!showSg && !showLed)) return `<div class="extra-config hidden"></div>`;

    let inner = "";
    if (showSg) {
      inner += `
        <div class="config-field">
          <label>Scene Group</label>
          <input id="inp-scene-group" type="text" value="${this._esc(btnCfg.scene_group || "")}" placeholder="e.g. living_room" style="min-width:120px">
        </div>`;
    }
    if (showLed) {
      inner += `
        <div class="config-field">
          <label>LED Switch Override</label>
          <input id="inp-led-entity" type="text" value="${this._esc(btnCfg.led_entity || "")}" placeholder="switch.keypad_led_1" style="min-width:160px">
        </div>`;
    }
    return `<div class="extra-config">${inner}</div>`;
  }

  // ── Entity tree ────────────────────────────────────────────────

  _renderTreeSection(entry, btnCfg, isRL) {
    const at = btnCfg.action_type || "none";
    const info = ACTION_TYPES[at];
    const domains = info?.domains || [];

    if (isRL || domains.length === 0) {
      const msg = isRL
        ? "Raise/Lower buttons use the last active button's context — no direct assignment needed."
        : at === "none"
          ? "Select an Action Type above to assign entities."
          : "This action type requires no entity assignment.";
      return `<div class="tree-section"><div class="tree-empty">${msg}</div></div>`;
    }

    const esq = (this._entitySearch || "").toLowerCase().trim();
    const allEntities = this._getEntitiesForAction(at);
    const entities = esq
      ? allEntities.filter(e => e.name.toLowerCase().includes(esq) || e.entity_id.toLowerCase().includes(esq))
      : allEntities;
    const byArea = this._groupByArea(entities);
    const areaKeys = Object.keys(byArea).sort((a, b) => {
      if (a === "_none") return 1; if (b === "_none") return -1;
      return areaName(this._hass, a).localeCompare(areaName(this._hass, b));
    });

    const isMulti = info?.multi || false;
    const selectedTargets = this._getSelectedTargets(btnCfg);

    const areaOpts = areaKeys
      .filter(k => k !== "_none")
      .map(k => `<option value="${k}" ${k === this._filterArea ? "selected" : ""}>${areaName(this._hass, k)}</option>`)
      .join("");

    let treeHtml = "";
    for (const areaId of areaKeys) {
      if (this._filterArea && areaId !== this._filterArea && areaId !== "_none") continue;
      const areaEntities = byArea[areaId];
      const expanded = this._expandedAreas.has(areaId);
      const selCount = areaEntities.filter(e => selectedTargets.includes(e.entity_id)).length;
      const allSel = selCount === areaEntities.length && areaEntities.length > 0;
      const someSel = selCount > 0 && !allSel;
      const label = areaId === "_none" ? "No Area" : areaName(this._hass, areaId);

      treeHtml += `
        <div class="area-node">
          <div class="area-header" data-area-toggle="${areaId}">
            <span class="area-expand">${expanded ? "▼" : "▶"}</span>
            <input type="checkbox" class="area-check" data-area-check="${areaId}"
                   ${allSel ? "checked" : ""} ${someSel ? "data-indeterminate" : ""}>
            <span class="area-name">${this._esc(label)}</span>
            <span class="area-count">${selCount > 0 ? selCount + " of " : ""}${areaEntities.length} ${selCount > 0 ? "selected" : "available"}</span>
          </div>
          <div class="area-entities ${expanded ? "open" : ""}" id="area-ents-${areaId}">
            ${areaEntities.map(ent => this._renderEntityRow(ent, selectedTargets, isMulti)).join("")}
          </div>
        </div>`;
    }

    if (!treeHtml) treeHtml = `<div class="tree-empty">No entities found for this action type.</div>`;

    return `
      <div class="tree-section">
        <div class="tree-search-wrap">
          <input type="search" id="entity-search" placeholder="Search entities…" value="${this._esc(this._entitySearch)}">
        </div>
        <div class="tree-filter-bar">
          <label>Show in:</label>
          <select id="sel-filter-area">
            <option value="">All Areas</option>
            ${areaOpts}
          </select>
          <button class="expand-all" id="btn-expand-all">Expand All</button>
        </div>
        <div class="tree-container">${treeHtml}</div>
      </div>`;
  }

  _renderEntityRow(ent, selectedTargets, isMulti) {
    const sel = selectedTargets.includes(ent.entity_id);
    const stateVal = this._hass.states?.[ent.entity_id]?.state;
    const attrs = this._hass.states?.[ent.entity_id]?.attributes || {};
    const stateLabel = entityStateLabel(ent.entity_id, stateVal, attrs);
    const icon = entityIcon(ent.entity_id, stateVal);
    const isOn = stateVal && !["off","closed","unavailable","unknown"].includes(stateVal);
    const inputType = isMulti ? "checkbox" : "radio";
    const inputName = isMulti ? "" : `name="radio-entity-${this._selectedEntryId}-${this._selectedButton}"`;

    return `
      <div class="entity-row ${sel ? "selected" : ""}" data-entity="${ent.entity_id}">
        <input type="${inputType}" ${inputName} class="entity-check" ${sel ? "checked" : ""}
               data-entity-check="${ent.entity_id}">
        <span class="entity-icon">${icon}</span>
        <span class="entity-name">${this._esc(ent.name)}</span>
        <span class="entity-state ${isOn ? "on" : ""}">${stateLabel}</span>
      </div>`;
  }

  // ── Summary / Programming table (bottom) ──────────────────────

  _renderSummarySection(entry, btnCfg, isRL, activeTab = "press_on") {
    const at = btnCfg.action_type || "none";
    const info = ACTION_TYPES[at];
    const targets = this._getSelectedTargets(btnCfg);
    const entSettings = btnCfg.entity_settings || {};

    // For raise/lower and none: simple info message
    if (isRL || at === "none") {
      const msg = isRL
        ? "Raise/Lower buttons inherit context from the last active button."
        : "No action configured for this button.";
      return `
        <div class="summary-section" id="summary-section" style="height:${this._summaryHeight}px">
          <div class="summary-header"><span>Programming — Button ${this._selectedButton}</span></div>
          <div class="summary-empty">${msg}</div>
        </div>`;
    }

    if (targets.length === 0) {
      const hint = info?.domains?.length
        ? `Select ${info.multi ? "one or more entities" : "an entity"} from the panel above to assign to this button.`
        : "";
      return `
        <div class="summary-section" id="summary-section" style="height:${this._summaryHeight}px">
          <div class="summary-header"><span>Programming — Button ${this._selectedButton} (${info?.label || at})</span></div>
          <div class="summary-empty">No entities assigned.${hint ? " " + hint : ""}</div>
        </div>`;
    }

    // Determine which capability columns to show
    const isEntityToggle = at === "entity_toggle";
    const isPressOnTab = activeTab === "press_on" || activeTab === undefined;
    let hasAnyBri = false, hasAnyCT = false, hasAnyColor = false;
    if (isEntityToggle) {
      for (const eid of targets) {
        const caps = getLightCaps(this._hass, eid);
        if (caps?.brightness) hasAnyBri = true;
        if (caps?.colorTemp)  hasAnyCT = true;
        if (caps?.color)      hasAnyColor = true;
      }
    }

    const colHeaders = `
      <th>Entity</th>
      <th>Current</th>
      ${hasAnyBri   ? "<th>Brightness&nbsp;%</th>" : ""}
      ${hasAnyCT    ? "<th>Color&nbsp;Temp&nbsp;K</th>" : ""}
      ${hasAnyColor ? "<th>Color</th>" : ""}
      ${(isEntityToggle && isPressOnTab) ? "<th>Fade&nbsp;s</th><th>Delay&nbsp;s</th>" : ""}
      <th></th>`;

    const rows = targets.map(entityId => {
      const stateObj = this._hass.states?.[entityId];
      const stateVal = stateObj?.state;
      const attrs = stateObj?.attributes || {};
      const entEntry = this._hass.entities?.[entityId];
      const name = friendlyName(this._hass, entityId, entEntry);
      const areaId = resolveAreaId(entityId, this._hass);
      const area = areaId ? areaName(this._hass, areaId) : "";
      const domain = entityId.split(".")[0];
      const domLabel = DOMAIN_LABELS[domain] || domain;
      const stateLabel = entityStateLabel(entityId, stateVal, attrs);
      const isOn = stateVal && !["off","closed","unavailable","unknown"].includes(stateVal);
      const desc = area ? `${area} › ${name}` : name;
      const caps = getLightCaps(this._hass, entityId);
      const ent_s = entSettings[entityId] || {};

      let briCell = "", ctCell = "", colorCell = "", fadeCell = "", delayCell = "";
      if (isEntityToggle) {
        if (hasAnyBri) {
          if (caps?.brightness) {
            const val = ent_s.brightness > 0 ? ent_s.brightness : "";
            briCell = `<td><input class="ent-setting" type="number" min="1" max="100"
                         data-entity="${entityId}" data-key="brightness"
                         value="${val}" placeholder="—" title="Target brightness %"></td>`;
          } else {
            briCell = `<td><span class="no-cap">—</span></td>`;
          }
        }
        if (hasAnyCT) {
          if (caps?.colorTemp) {
            const val = ent_s.color_temp > 0 ? ent_s.color_temp : "";
            ctCell = `<td><input class="ent-setting" type="number" min="1500" max="9000" step="50"
                        data-entity="${entityId}" data-key="color_temp"
                        value="${val}" placeholder="—" title="Target color temperature in Kelvin"></td>`;
          } else {
            ctCell = `<td><span class="no-cap">—</span></td>`;
          }
        }
        if (hasAnyColor) {
          if (caps?.color) {
            const hs = ent_s.hs_color;
            const hexVal = hs ? hsToHex(hs[0], hs[1]) : "#ffffff";
            const hasColor = hs && (hs[0] !== 0 || hs[1] !== 0);
            colorCell = `<td>
              <input class="ent-color-input" type="color"
                     data-entity="${entityId}" data-key="hs_color"
                     value="${hexVal}" title="Target color"
                     style="${hasColor ? "" : "opacity:0.35"}">
            </td>`;
          } else {
            colorCell = `<td><span class="no-cap">—</span></td>`;
          }
        }
        if (isPressOnTab) {
          const fadeVal  = ent_s.fade  > 0 ? ent_s.fade  : "";
          const delayVal = ent_s.delay > 0 ? ent_s.delay : "";
          fadeCell  = `<td><input class="ent-setting" type="number" min="0" max="60" step="0.5"
                          data-entity="${entityId}" data-key="fade"
                          value="${fadeVal}" placeholder="0" title="Transition time in seconds"></td>`;
          delayCell = `<td><input class="ent-setting" type="number" min="0" max="30" step="0.5"
                          data-entity="${entityId}" data-key="delay"
                          value="${delayVal}" placeholder="0" title="Delay before sending command (seconds)"></td>`;
        }
      }

      return `
        <tr>
          <td>
            <span class="type-badge">${domLabel}</span>
            <span style="margin-left:6px;font-size:12px">${this._esc(desc)}</span>
          </td>
          <td class="${isOn ? "state-on" : ""}" style="white-space:nowrap">${stateLabel || "—"}</td>
          ${briCell}${ctCell}${colorCell}${fadeCell}${delayCell}
          <td><button class="remove-entity" data-remove="${entityId}" title="Remove">✕</button></td>
        </tr>`;
    }).join("");

    const capHint = isEntityToggle && (hasAnyBri || hasAnyCT || hasAnyColor)
      ? `<span class="cap-hint">Per-fixture targets applied when turning on</span>`
      : "";

    return `
      <div class="summary-section" id="summary-section" style="height:${this._summaryHeight}px">
        <div class="summary-header">
          <span>Programming — Button ${this._selectedButton} (${info?.label || at})</span>
          ${capHint}
        </div>
        <table class="summary-table">
          <thead><tr>${colHeaders}</tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
  }

  // ── Event wiring ───────────────────────────────────────────────

  _attachMainListeners(entry, buttons, btnCfg) {
    const shadow = this._shadow;

    // Keypad button clicks
    shadow.querySelectorAll("[data-kp-btn]").forEach(el => {
      el.addEventListener("click", () => {
        this._selectedButton = parseInt(el.dataset.kpBtn, 10);
        this._renderMain();
      });
    });

    // Prev/Next navigation
    const prev = shadow.getElementById("btn-prev");
    const next = shadow.getElementById("btn-next");
    if (prev) prev.addEventListener("click", () => {
      const n = parseInt(prev.dataset.prev, 10);
      if (!isNaN(n)) { this._selectedButton = n; this._renderMain(); }
    });
    if (next) next.addEventListener("click", () => {
      const n = parseInt(next.dataset.next, 10);
      if (!isNaN(n)) { this._selectedButton = n; this._renderMain(); }
    });

    // Label
    const inpLabel = shadow.getElementById("inp-label");
    if (inpLabel) {
      inpLabel.addEventListener("change", () => {
        this._setBtnProp("label", inpLabel.value);
        const newLabel = inpLabel.value || `Btn ${this._selectedButton}`;
        shadow.querySelectorAll(`[data-kp-btn="${this._selectedButton}"]`).forEach(el => {
          if (el.classList.contains("raise-lower")) return;
          const engravingSpan = el.querySelector(".kp-btn-engraving");
          if (engravingSpan) engravingSpan.textContent = newLabel;
          else el.textContent = newLabel;
        });
      });
    }

    // Tab bar
    shadow.querySelectorAll(".tab-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        this._setActiveTab(btn.dataset.tab);
        this._renderMain();
      });
    });

    // Press On action type (in press_on tab)
    const selAction = shadow.getElementById("sel-action-type");
    if (selAction) {
      selAction.addEventListener("change", () => {
        this._setBtnProp("action_type", selAction.value);
        this._setBtnProp("action_target", "");
        this._renderMain();
      });
    }

    // Sub-tab action type selectors (double_tap / hold)
    shadow.querySelectorAll("[id^='sel-sub-action-']").forEach(sel => {
      sel.addEventListener("change", () => {
        const tabName = sel.dataset.tab;
        this._setTabProp(tabName, "action_type", sel.value);
        this._setTabProp(tabName, "action_target", "");
        this._renderMain();
      });
    });

    // LED logic
    const selLed = shadow.getElementById("sel-led-logic");
    if (selLed) selLed.addEventListener("change", () => this._setBtnProp("led_mode", selLed.value));

    // Cycle dim
    const chkCycle = shadow.getElementById("chk-cycle-dim");
    if (chkCycle) chkCycle.addEventListener("change", () => this._setBtnProp("cycle_dim", chkCycle.checked));

    // LED invert
    const chkInvert = shadow.getElementById("chk-led-invert");
    if (chkInvert) chkInvert.addEventListener("change", () => this._setBtnProp("led_invert", chkInvert.checked));

    // Extra config (stateful_scene)
    const inpSG = shadow.getElementById("inp-scene-group");
    if (inpSG) inpSG.addEventListener("change", () => this._setBtnProp("scene_group", inpSG.value.trim()));
    const inpLedEnt = shadow.getElementById("inp-led-entity");
    if (inpLedEnt) inpLedEnt.addEventListener("change", () => this._setBtnProp("led_entity", inpLedEnt.value.trim()));

    // Entity search
    const entSearch = shadow.getElementById("entity-search");
    if (entSearch) {
      entSearch.addEventListener("input", e => {
        this._entitySearch = e.target.value;
        this._renderMain();
      });
    }

    // Area filter
    const selArea = shadow.getElementById("sel-filter-area");
    if (selArea) {
      selArea.addEventListener("change", () => {
        this._filterArea = selArea.value;
        this._renderMain();
      });
    }

    // Expand all
    const btnExpand = shadow.getElementById("btn-expand-all");
    if (btnExpand) {
      btnExpand.addEventListener("click", () => {
        const at = (this._pendingConfig[this._selectedEntryId] || {})[this._selectedButton]?.action_type || "none";
        const entities = this._getEntitiesForAction(at);
        const byArea = this._groupByArea(entities);
        const allExpanded = Object.keys(byArea).every(k => this._expandedAreas.has(k));
        if (allExpanded) Object.keys(byArea).forEach(k => this._expandedAreas.delete(k));
        else Object.keys(byArea).forEach(k => this._expandedAreas.add(k));
        this._renderMain();
      });
    }

    // Area toggle
    shadow.querySelectorAll("[data-area-toggle]").forEach(el => {
      el.addEventListener("click", (e) => {
        if (e.target.type === "checkbox") return;
        const areaId = el.dataset.areaToggle;
        if (this._expandedAreas.has(areaId)) this._expandedAreas.delete(areaId);
        else this._expandedAreas.add(areaId);
        this._renderMain();
      });
    });

    // Area checkboxes (press_on tree)
    shadow.querySelectorAll("[data-area-check]:not(.sub-area-check)").forEach(el => {
      el.addEventListener("change", (e) => {
        e.stopPropagation();
        const areaId = el.dataset.areaCheck;
        const at = (this._pendingConfig[this._selectedEntryId] || {})[this._selectedButton]?.action_type || "none";
        const entities = this._getEntitiesForAction(at);
        const areaEnts = entities.filter(ent => (resolveAreaId(ent.entity_id, this._hass) || "_none") === areaId);
        areaEnts.forEach(ent => this._selectEntity(ent.entity_id, el.checked));
        this._renderMain();
      });
    });

    // Sub-tab area checkboxes (double_tap / hold)
    shadow.querySelectorAll(".sub-area-check").forEach(el => {
      el.addEventListener("change", (e) => {
        e.stopPropagation();
        const areaId = el.dataset.areaCheck;
        const tabName = el.dataset.tab;
        const tabCfg = (this._pendingConfig[this._selectedEntryId] || {})[this._selectedButton]?.[tabName] || {};
        const at = tabCfg.action_type || "none";
        const entities = this._getEntitiesForAction(at);
        const areaEnts = entities.filter(ent => (resolveAreaId(ent.entity_id, this._hass) || "_none") === areaId);
        areaEnts.forEach(ent => this._selectTabEntity(tabName, ent.entity_id, el.checked));
        this._renderMain();
      });
    });

    // Entity checkboxes/radios (press_on tree)
    shadow.querySelectorAll("[data-entity-check]:not(.sub-entity-check)").forEach(el => {
      el.addEventListener("change", () => {
        const entityId = el.dataset.entityCheck;
        const at = (this._pendingConfig[this._selectedEntryId] || {})[this._selectedButton]?.action_type || "none";
        const isMulti = ACTION_TYPES[at]?.multi || false;
        if (!isMulti) this._setBtnProp("action_target", entityId);
        else this._selectEntity(entityId, el.checked);
        this._renderMain();
      });
    });

    // Sub-tab entity checkboxes (double_tap / hold)
    shadow.querySelectorAll(".sub-entity-check").forEach(el => {
      el.addEventListener("change", () => {
        const entityId = el.dataset.entityCheck;
        const tabName  = el.dataset.tab;
        const tabCfg = (this._pendingConfig[this._selectedEntryId] || {})[this._selectedButton]?.[tabName] || {};
        const at = tabCfg.action_type || "none";
        const isMulti = ACTION_TYPES[at]?.multi || false;
        if (!isMulti) this._setTabProp(tabName, "action_target", entityId);
        else this._selectTabEntity(tabName, entityId, el.checked);
        this._renderMain();
      });
    });

    // Entity row click (works for both main tree and sub-tabs)
    shadow.querySelectorAll(".entity-row").forEach(el => {
      el.addEventListener("click", (e) => {
        if (e.target.type === "checkbox" || e.target.type === "radio") return;
        const chk = el.querySelector("[data-entity-check]");
        if (chk) { chk.checked = !chk.checked; chk.dispatchEvent(new Event("change")); }
      });
    });

    // Remove from summary
    shadow.querySelectorAll("[data-remove]").forEach(el => {
      el.addEventListener("click", () => {
        this._selectEntity(el.dataset.remove, false);
        this._renderMain();
      });
    });

    // Per-entity setting inputs in summary (no re-render on change)
    shadow.querySelectorAll(".ent-setting:not(.ol-setting)").forEach(el => {
      el.addEventListener("change", () => {
        const entityId = el.dataset.entity;
        const key = el.dataset.key;
        const val = parseFloat(el.value) || 0;
        this._setEntitySetting(entityId, key, val > 0 ? val : null);
      });
    });

    // Off Level inputs
    shadow.querySelectorAll(".ol-setting").forEach(el => {
      el.addEventListener("change", () => {
        const entityId = el.dataset.entity;
        const val = parseInt(el.value) || 0;
        this._setOffLevelSetting(entityId, "brightness", val > 0 ? val : null);
      });
    });

    // Per-entity color inputs in summary
    shadow.querySelectorAll(".ent-color-input").forEach(el => {
      el.addEventListener("change", () => {
        const entityId = el.dataset.entity;
        const hs = hexToHs(el.value);
        el.style.opacity = (hs[0] === 0 && hs[1] === 0) ? "0.35" : "1";
        this._setEntitySetting(entityId, "hs_color", hs);
      });
    });

    // Set indeterminate state on area checkboxes
    shadow.querySelectorAll("[data-indeterminate]").forEach(el => { el.indeterminate = true; });

    // Init resizers (keypad and summary ones re-bound each render)
    this._initResizers();
  }

  // ── Resize handling ────────────────────────────────────────────

  _initResizers() {
    const shadow = this._shadow;

    if (!this._sidebarResizerBound) {
      const sidebarResizer = shadow.getElementById("sidebar-resizer");
      const sidebar = shadow.getElementById("sidebar");
      if (sidebarResizer && sidebar) {
        this._setupHorizontalResizer(sidebarResizer, sidebar, 140, 450, w => { this._sidebarWidth = w; });
        this._sidebarResizerBound = true;
      }
    }

    const keypayResizer = shadow.getElementById("keypad-resizer");
    const colKeypad = shadow.querySelector(".col-keypad");
    if (keypayResizer && colKeypad) {
      this._setupHorizontalResizer(keypayResizer, colKeypad, 120, 380, w => { this._keypayWidth = w; });
    }

    const summaryResizer = shadow.getElementById("summary-resizer");
    const summarySection = shadow.getElementById("summary-section");
    if (summaryResizer && summarySection) {
      this._setupVerticalResizer(summaryResizer, summarySection, 60, 600, h => { this._summaryHeight = h; });
    }
  }

  _setupHorizontalResizer(handle, target, min, max, onResize) {
    let startX, startW;
    handle.addEventListener("mousedown", e => {
      startX = e.clientX; startW = target.getBoundingClientRect().width;
      handle.classList.add("dragging");
      const onMove = ev => {
        const w = Math.max(min, Math.min(max, startW + ev.clientX - startX));
        target.style.width = w + "px"; onResize(w);
      };
      const onUp = () => {
        handle.classList.remove("dragging");
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
      e.preventDefault();
    });
  }

  _setupVerticalResizer(handle, target, min, max, onResize) {
    let startY, startH;
    handle.addEventListener("mousedown", e => {
      startY = e.clientY; startH = target.getBoundingClientRect().height;
      handle.classList.add("dragging");
      const onMove = ev => {
        const h = Math.max(min, Math.min(max, startH + startY - ev.clientY));
        target.style.height = h + "px"; onResize(h);
      };
      const onUp = () => {
        handle.classList.remove("dragging");
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
      e.preventDefault();
    });
  }

  // ── State helpers ──────────────────────────────────────────────

  _getEntry(entryId) { return this._entries.find(e => e.entry_id === entryId); }

  _setBtnProp(key, value) {
    const entryId = this._selectedEntryId;
    if (!this._pendingConfig[entryId]) return;
    if (!this._pendingConfig[entryId][this._selectedButton])
      this._pendingConfig[entryId][this._selectedButton] = defaultBtnCfg();
    this._pendingConfig[entryId][this._selectedButton][key] = value;
    this._dirty[entryId] = true;
    this._updateSaveButton();
  }

  _setEntitySetting(entityId, key, value) {
    const entryId = this._selectedEntryId;
    if (!entryId || !this._pendingConfig[entryId]) return;
    const btnCfg = this._pendingConfig[entryId][this._selectedButton];
    if (!btnCfg) return;
    if (!btnCfg.entity_settings) btnCfg.entity_settings = {};
    if (!btnCfg.entity_settings[entityId]) btnCfg.entity_settings[entityId] = {};
    if (value === null || value === undefined || value === 0) {
      delete btnCfg.entity_settings[entityId][key];
    } else {
      btnCfg.entity_settings[entityId][key] = value;
    }
    this._dirty[entryId] = true;
    this._updateSaveButton();
  }

  _setTabProp(tabName, key, value) {
    const entryId = this._selectedEntryId;
    if (!entryId || !this._pendingConfig[entryId]) return;
    const btnCfg = this._pendingConfig[entryId][this._selectedButton];
    if (!btnCfg) return;
    if (!btnCfg[tabName]) btnCfg[tabName] = { action_type: "none", action_target: "", entity_settings: {} };
    btnCfg[tabName][key] = value;
    this._dirty[entryId] = true;
    this._updateSaveButton();
  }

  _selectTabEntity(tabName, entityId, selected) {
    const entryId = this._selectedEntryId;
    if (!entryId || !this._pendingConfig[entryId]) return;
    const btnCfg = this._pendingConfig[entryId][this._selectedButton];
    if (!btnCfg) return;
    if (!btnCfg[tabName]) btnCfg[tabName] = { action_type: "none", action_target: "", entity_settings: {} };
    const tabCfg = btnCfg[tabName];
    const at = tabCfg.action_type || "none";
    const isMulti = ACTION_TYPES[at]?.multi || false;
    if (!isMulti) {
      tabCfg.action_target = selected ? entityId : "";
    } else {
      let targets = Array.isArray(tabCfg.action_target)
        ? [...tabCfg.action_target]
        : (tabCfg.action_target ? [tabCfg.action_target] : []);
      if (selected) { if (!targets.includes(entityId)) targets.push(entityId); }
      else targets = targets.filter(t => t !== entityId);
      tabCfg.action_target = targets;
    }
    this._dirty[entryId] = true;
    this._updateSaveButton();
  }

  _setOffLevelSetting(entityId, key, value) {
    const entryId = this._selectedEntryId;
    if (!entryId || !this._pendingConfig[entryId]) return;
    const btnCfg = this._pendingConfig[entryId][this._selectedButton];
    if (!btnCfg) return;
    if (!btnCfg.off_level) btnCfg.off_level = { entity_settings: {} };
    if (!btnCfg.off_level.entity_settings) btnCfg.off_level.entity_settings = {};
    if (!btnCfg.off_level.entity_settings[entityId]) btnCfg.off_level.entity_settings[entityId] = {};
    if (value === null || value === undefined || value === 0) {
      delete btnCfg.off_level.entity_settings[entityId][key];
    } else {
      btnCfg.off_level.entity_settings[entityId][key] = value;
    }
    this._dirty[entryId] = true;
    this._updateSaveButton();
  }

  _selectEntity(entityId, selected) {
    const entryId = this._selectedEntryId;
    if (!entryId || !this._pendingConfig[entryId]) return;
    const btnCfg = this._pendingConfig[entryId][this._selectedButton];
    if (!btnCfg) return;

    const at = btnCfg.action_type || "none";
    const isMulti = ACTION_TYPES[at]?.multi || false;

    if (!isMulti) {
      btnCfg.action_target = selected ? entityId : "";
    } else {
      let targets = Array.isArray(btnCfg.action_target)
        ? [...btnCfg.action_target]
        : (btnCfg.action_target ? [btnCfg.action_target] : []);
      if (selected) { if (!targets.includes(entityId)) targets.push(entityId); }
      else targets = targets.filter(t => t !== entityId);
      btnCfg.action_target = targets;
    }
    this._dirty[entryId] = true;
    this._updateSaveButton();
  }

  _getSelectedTargets(btnCfg) {
    const raw = btnCfg.action_target;
    if (!raw) return [];
    if (Array.isArray(raw)) return raw.filter(Boolean);
    if (typeof raw === "string" && raw.includes(",")) return raw.split(",").map(s => s.trim()).filter(Boolean);
    if (typeof raw === "string" && raw) return [raw];
    return [];
  }

  _getEntitiesForAction(actionType) {
    const info = ACTION_TYPES[actionType];
    if (!info || !info.domains.length) return [];
    const result = [];
    for (const [entityId, ent] of Object.entries(this._hass.entities || {})) {
      if (!info.domains.some(d => entityId.startsWith(d + "."))) continue;
      result.push({ entity_id: entityId, name: friendlyName(this._hass, entityId, ent) });
    }
    result.sort((a, b) => a.name.localeCompare(b.name));
    return result;
  }

  _groupByArea(entities) {
    const byArea = {};
    for (const ent of entities) {
      const areaId = resolveAreaId(ent.entity_id, this._hass) || "_none";
      if (!byArea[areaId]) byArea[areaId] = [];
      byArea[areaId].push(ent);
    }
    return byArea;
  }

  // ── Save ──────────────────────────────────────────────────────

  _updateSaveButton() {
    const btn = this._shadow.getElementById("btn-save");
    if (btn) btn.disabled = !this._dirty[this._selectedEntryId];
  }

  async _saveConfig() {
    const entryId = this._selectedEntryId;
    if (!entryId) return;

    const pending = this._pendingConfig[entryId] || {};
    const buttons = {};
    for (const [btnNum, cfg] of Object.entries(pending)) buttons[String(btnNum)] = cfg;

    const saveBtn = this._shadow.getElementById("btn-save");
    const statusEl = this._shadow.getElementById("save-status");
    if (saveBtn) saveBtn.disabled = true;
    if (statusEl) statusEl.textContent = "Saving…";

    try {
      await this._hass.callWS({
        type: "lutron_keypad_controller/save_keypad_config",
        entry_id: entryId, buttons,
      });
      this._dirty[entryId] = false;
      if (statusEl) {
        statusEl.textContent = "✓ Saved";
        setTimeout(() => { if (statusEl) statusEl.textContent = ""; }, 3000);
      }
      await this._loadEntries();
      this._renderSidebar();
    } catch (e) {
      console.error("LutronPanel: save failed", e);
      if (statusEl) statusEl.textContent = "⚠ Save failed";
      if (saveBtn) saveBtn.disabled = false;
    }
  }

  // ── Add Keypad dialog ─────────────────────────────────────────

  async _showAddDialog() {
    const overlay = this._shadow.getElementById("modal-overlay");
    const body = this._shadow.getElementById("modal-body");
    if (!overlay || !body) return;
    overlay.classList.remove("hidden");
    this._selectedDiscoveryDevice = null;
    body.innerHTML = `<div class="modal-loading">Discovering keypads…</div>`;
    try {
      const devices = await this._hass.callWS({ type: "lutron_keypad_controller/discover_keypads" });
      body.innerHTML = this._renderDiscoveryBody(devices);
      this._attachDialogListeners(devices);
    } catch (e) {
      body.innerHTML = `<div class="modal-error">Discovery failed: ${this._esc(String(e?.message || e))}</div>`;
    }
  }

  _closeDialog() {
    const overlay = this._shadow.getElementById("modal-overlay");
    if (overlay) overlay.classList.add("hidden");
    this._selectedDiscoveryDevice = null;
  }

  _renderDiscoveryBody(devices) {
    if (!devices || devices.length === 0) {
      return `<div class="modal-empty">No new keypads found. All Lutron devices may already be configured.</div>`;
    }
    const cards = devices.map((d, i) => `
      <div class="device-card" data-di="${i}">
        <div class="device-card-main">
          <span class="device-card-name">${this._esc(d.name || d.serial)}</span>
          <span class="device-card-area">${this._esc(d.area || "")}</span>
        </div>
        <div class="device-card-meta">
          <span class="device-card-type">${this._esc(d.type || "")}</span>
          ${d.model ? `<span class="device-card-model">${this._esc(d.model)}</span>` : ""}
        </div>
      </div>`).join("");
    return `
      <p class="modal-hint">Select a keypad to add:</p>
      <div class="modal-devices">${cards}</div>
      <div class="modal-add-form hidden" id="modal-add-form">
        <label>Display Name</label>
        <input id="modal-name-input" type="text" placeholder="e.g. Living Room Main">
        <div class="modal-error hidden" id="modal-error"></div>
        <div class="modal-form-actions">
          <button class="modal-btn-cancel" id="modal-btn-cancel">Cancel</button>
          <button class="modal-btn-confirm" id="modal-btn-confirm">Add Keypad</button>
        </div>
      </div>`;
  }

  _attachDialogListeners(devices) {
    const shadow = this._shadow;
    shadow.querySelectorAll(".device-card").forEach((card, i) => {
      card.addEventListener("click", () => {
        shadow.querySelectorAll(".device-card").forEach(c => c.classList.remove("selected"));
        card.classList.add("selected");
        this._selectedDiscoveryDevice = devices[i];
        const form = shadow.getElementById("modal-add-form");
        const nameInput = shadow.getElementById("modal-name-input");
        if (form) form.classList.remove("hidden");
        if (nameInput) { nameInput.value = devices[i].name || ""; nameInput.focus(); nameInput.select(); }
      });
    });
    const cancelBtn = shadow.getElementById("modal-btn-cancel");
    if (cancelBtn) cancelBtn.addEventListener("click", () => this._closeDialog());
    const confirmBtn = shadow.getElementById("modal-btn-confirm");
    if (confirmBtn) confirmBtn.addEventListener("click", () => this._confirmAddKeypad());
    const nameInput = shadow.getElementById("modal-name-input");
    if (nameInput) {
      nameInput.addEventListener("keydown", e => { if (e.key === "Enter") this._confirmAddKeypad(); });
    }
  }

  async _confirmAddKeypad() {
    const device = this._selectedDiscoveryDevice;
    if (!device) return;
    const shadow = this._shadow;
    const nameInput = shadow.getElementById("modal-name-input");
    const name = (nameInput?.value || "").trim() || device.name || device.serial;
    const errorEl = shadow.getElementById("modal-error");
    const confirmBtn = shadow.getElementById("modal-btn-confirm");
    if (confirmBtn) confirmBtn.disabled = true;
    if (errorEl) errorEl.classList.add("hidden");
    try {
      await this._hass.callWS({
        type: "lutron_keypad_controller/add_keypad",
        serial: device.serial,
        name,
        device_id: device.device_id || "",
      });
      this._closeDialog();
      await this._loadEntries();
      this._renderSidebar();
    } catch (e) {
      if (errorEl) {
        errorEl.textContent = String(e?.message || e || "Add failed");
        errorEl.classList.remove("hidden");
      }
      if (confirmBtn) confirmBtn.disabled = false;
    }
  }

  // ── Utilities ─────────────────────────────────────────────────

  _esc(str) {
    return String(str || "")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
}

customElements.define("lutron-keypad-panel", LutronKeypadsPanel);
