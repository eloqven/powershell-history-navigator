---
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-plan
execution: code
title: "PowerShell History Navigator - Advanced TUI Enhancements & In-Place Editing Plan"
date: "2026-09-20"
authors: ["eloqven", "Antigravity"]
---

# Technical Implementation Plan: Advanced TUI Enhancements & In-Place Editing

## Goal Capsule
- **Objective**: Elevate the user experience of PowerShell History Navigator by implementing full-screen immersive theme styling, `:` quick-filter activation, an in-place command modification modal (`M`), and a configurable/toggleable history sorting & bottom-selection engine (`S`).
- **Means**: Expand Textual CSS custom styling across all widgets, create an interactive `EditCommandModal`, add keybinding handlers for `:` and `M`, and implement dynamic cursor positioning & sorting direction toggle in `history_tui.py`.
- **Authority Hierarchy**:
  1. Data Integrity: Never corrupt `ConsoleHost_history.txt` during in-place edits or deletions.
  2. Non-blocking UX: Retain sub-50ms keystroke responsiveness with no lag during theme switches or search queries.
  3. Elegance & Ergonomics: Ensure intuitive keyboard workflows without key clashing.
- **Stop Conditions**: All 4 feature units implemented, passing 100% of pytest test suites, verified in live TUI, committed, and pushed to GitHub.

---

## Product Contract

### Requirements
1. **REQ-1 (Full-TUI Immersive Theming)**:
   - Theme toggle (`T`) must recolor the *entire* interface, including:
     - Screen background & panel backgrounds
     - DataTable header bar (`.datatable--header`)
     - DataTable cursor row highlight (`.datatable--cursor`) with distinct foreground & background
     - Search input border & focused outline
     - Code preview borders and syntax highlighting
   - Support **Monokai**, **Dracula**, and a newly added **Tokyo Night / Nord** palette.

2. **REQ-2 (Quick-Filter on `:` / `Shift + ;`)**:
   - Pressing `:` anywhere in the app immediately focuses the `#search_input` bar and prepends `:` so users can type `:red:`, `:err`, etc., with zero friction.

3. **REQ-3 (In-Place Command Editing Modal `M`)**:
   - Pressing `M` (or `I`) opens an in-place editing modal pre-populated with the full text of the currently selected command.
   - User can modify the command (fix typos, update arguments/paths).
   - Modal actions:
     - `Ctrl + S` or `Enter`: Save updated command in-place directly to `ConsoleHost_history.txt` on disk.
     - `C`: Copy modified command to clipboard and exit.
     - `Esc`: Discard changes and return to table without altering history.

4. **REQ-4 (Configurable Sort Direction & Bottom Preselection `S`)**:
   - Support two navigation models toggleable via `S` (Sort Order):
     - **Model A (Reverse-Chronological, Default)**: Newest commands at Row #1 (Top), cursor preselected at Top.
     - **Model B (Chronological / Classic Terminal Mode)**: Oldest commands at Top, Newest command at the very Bottom (Row #N), cursor automatically preselecting and scrolling to the bottom on load.

---

## Planning Contract

### Technical Design

#### 1. Theme Engine & Deep CSS Selectors
```css
/* Monokai Full Immersion */
Screen.theme-monokai {
    background: #272822;
    color: #f8f8f2;
}
Screen.theme-monokai DataTable > .datatable--header {
    background: #1e1f1c;
    color: #66d9ef;
    text-style: bold;
}
Screen.theme-monokai DataTable > .datatable--cursor {
    background: #3e3d32;
    color: #a6e22e;
    text-style: bold;
}
Screen.theme-monokai #search_input:focus {
    border: double #f92672;
    background: #1e1f1c;
}

/* Dracula Full Immersion */
Screen.theme-dracula {
    background: #282a36;
    color: #f8f8f2;
}
Screen.theme-dracula DataTable > .datatable--header {
    background: #1e1f29;
    color: #8be9fd;
    text-style: bold;
}
Screen.theme-dracula DataTable > .datatable--cursor {
    background: #44475a;
    color: #50fa7b;
    text-style: bold;
}
Screen.theme-dracula #search_input:focus {
    border: double #ff79c6;
    background: #1e1f29;
}
```

#### 2. In-Place Edit Modal Architecture (`EditCommandModal`)
- Subclass `ModalScreen[Optional[Tuple[str, str]]]` returning action type (`"save"`, `"copy"`, or `None`) and modified command text.
- Contains:
  - Header: `✏️ Edit Command #{index}`
  - `TextArea` / `Input` for editing
  - Button Row: `[ Save to Disk (Ctrl+S) ]`, `[ Copy & Exit (Ctrl+C/Enter) ]`, `[ Cancel (Esc) ]`
- On dismissal with `"save"`, update `self.all_commands[real_idx] = new_text`, recompute `self.dud_flags[real_idx]`, save to disk, and refresh table.

#### 3. Quick-Colon Filter Handler
- Keybinding: `Binding("colon", "focus_colon_search", "Filter (:)", show=False)`
- Method:
  ```python
  def action_focus_colon_search(self) -> None:
      inp = self.query_one("#search_input", SearchInput)
      inp.focus()
      if not inp.value.startswith(":"):
          inp.value = ":" + inp.value
          inp.cursor_position = len(inp.value)
  ```

---

## Implementation Units

### U-01: Full-TUI Theme Immersion & Deep Palette Selectors
- **Files**: `history_tui.py`
- **Work**:
  - Add deep CSS rules for `.datatable--header`, `.datatable--cursor`, `#preview_container`, `#search_box`, and `#search_input`.
  - Add third theme: `tokyonight` (vibrant indigo/cyan palette).
- **Verification**: Press `T` and verify header, cursor highlight, preview border, and search box all transform seamlessly.

### U-02: Quick `:` Filter Keybinding
- **Files**: `history_tui.py`
- **Work**:
  - Add binding for `colon` / `:` key.
  - Implement `action_focus_colon_search()` to focus input and prepopulate `:`.
- **Verification**: Press `:` from table -> search bar receives focus with `:` typed.

### U-03: In-Place Command Editor Modal (`M`)
- **Files**: `history_tui.py`, `tests/test_dud_classifier.py`
- **Work**:
  - Create `EditCommandModal(ModalScreen)` with editing box and save/copy actions.
  - Implement `action_edit_command()` in `HistoryDashboard`.
  - Add disk write-back and UI refresh.
- **Verification**: Select a command, press `M`, change text, press `Ctrl+S`, verify updated command persists in `ConsoleHost_history.txt` and updates in preview.

### U-04: Sort Direction & Bottom Selection Engine (`S`)
- **Files**: `history_tui.py`
- **Work**:
  - Add `sort_newest_first: bool = reactive(True)` and `Binding("s", "toggle_sort_order", "Sort Order (S)")`.
  - In `apply_filter()`, order indices ascending or descending based on `self.sort_newest_first`.
  - When switching to Oldest-First mode, automatically scroll and select the last row.
- **Verification**: Press `S` -> list inverts; cursor jumps to bottom on chronological mode and top on reverse-chronological mode.

---

## Verification Contract

- **Automated Tests**:
  - `pytest tests/` ensuring all classifier, parser, and utility tests pass with 0 regressions.
- **Manual TUI Verification**:
  1. `T` cycle: Monokai ➔ Dracula ➔ Tokyo Night.
  2. `:` trigger: Immediately activates search bar with `:`.
  3. `M` trigger: Modifies command text, saves to disk, updates table.
  4. `S` trigger: Toggles sorting order and cursor preselection.
- **Git & GitHub Release**:
  - Commit all updates with standardized semantic messages and push to `eloqven/powershell-history-navigator`.

---

## Definition of Done

- [x] Implementation plan documented and approved.
- [x] U-01 through U-04 implemented in `history_tui.py` (Full Theming, Command Mode `:`, In-Place Editor `M`, Sort Order `S`).
- [x] Unit & TUI interaction test suite created in `tests/test_tui_interactions.py` (9/9 tests passing).
- [ ] Pushed to GitHub repository.
