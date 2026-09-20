<div align="center">

<img src="./assets/logo.png" alt="PowerShell History Navigator" width="160" height="160" style="border-radius: 24px; margin-bottom: 12px;"/>

# PowerShell History Navigator & Cleaner (TUI)

**A high-performance terminal UI for inspecting, searching, syntax-validating, and pruning PowerShell history.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Built with Textual](https://img.shields.io/badge/built%20with-Textual-teal.svg)](https://textual.textualize.io/)
[![Platform Windows](https://img.shields.io/badge/platform-Windows%20%7C%20PowerShell-lightgrey.svg)](https://learn.microsoft.com/en-us/powershell/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

[Features](#-key-features) • [The Origin Story](#the-origin-story-why-this-exists) • [Architecture Deep-Dive](#under-the-hood-for-engineers--ai-agents) • [Installation](#-quickstart--installation) • [Keybindings](#keyboard-shortcuts--command-mode)

</div>

---

## The Origin Story: Why This Exists

If you use PowerShell heavily, you have likely encountered this terminal issue:

1. You paste a multi-line script, a large JSON payload, or an authentication token into the console.
2. Later, you press **`Up Arrow`** or use **`Ctrl + R` (Reverse Search)** to recall a previous command.
3. Suddenly, PowerShell's **PSReadLine** hits that multi-line block: the cursor jumps unpredictably across console rows, overwriting previous lines and getting stuck in a visual loop between 2–3 commands.
4. Because PSReadLine saves all commands directly to disk (`ConsoleHost_history.txt`), **this glitch persists across terminal restarts and never goes away on its own.**

**PowerShell History Navigator** provides a terminal interface (TUI) to browse, search, copy, edit, and remove commands from `ConsoleHost_history.txt` on disk.

---

## ✨ Key Features

- **Latest-First Ordering**: Inspect your command stream starting from your most recent command at the top, or toggle to classic terminal bottom-first order.
- **Instant Live Search & Filter**: Real-time incremental search bar docked at the bottom of the screen with instant `↑`/`↓` table navigation.
- **Vim-Style Command Mode (`:`)**: Press `:` to trigger 1-word commands like `:red`, `:edit`, `:sort`, `:theme`, `:purge`, and `:quit`.
- **Bad Syntax & Dud Detection (`:red`)**: A lexical state-machine identifies syntax errors, broken quotes, unmatched brackets, and pasted error tracebacks, highlighting them in bold red. Type `:red` to isolate all duds.
- **In-Place Command Editing (`M` / `:edit`)**: Pop open an interactive modal to edit typos or modify parameters in past commands directly before saving or copying.
- **Surgical & Bulk History Purging**:
  - Delete individual commands with `Delete` or `D` (triggered on key-up to prevent accidental repeats).
  - Delete **all filtered commands** at once with `X` or `:purge` (safeguarded by active filter requirements and double confirmation modals).
- **Full-TUI Theme Engine (`T` / `:theme`)**: Switch dynamically between **Monokai**, **Dracula**, and **Tokyo Night** across the entire UI layout.
- **Editor Integration (`E` / `:subl`)**: One-key jump directly into Sublime Text, VS Code, or your default text editor.
- **Direct Clipboard Copy (`Enter` / `C`)**: Hit `Enter` to copy the selected command to your Windows clipboard and exit immediately.
- **On-Screen Keymap Overlay (`?` / `H` / `F1`)**: Modal shortcut cheat-sheet accessible at any moment.

---

## Screenshots & Layout

```
┌────────────────────────────────────────────────────────────────────────┐
│  Command Preview (#4748 - 54 chars)                                    │
│  Get-ChildItem -Path C:\Projects -Recurse | Where-Object Length -gt 1MB│
├────────────────────────────────────────────────────────────────────────┤
│  #     Len   Command                                                   │
│  4748  74    Get-ChildItem -Path C:\Projects -Recurse | Where-Object...│
│  4747  18    git status                                                │
│  4746  32    python -m pytest tests/unit                               │
│  4745  104   [!] At line:10 char:1 + CategoryInfo : ObjectNotFound     │
│  4744  26    npm run build --prefix frontend                           │
├────────────────────────────────────────────────────────────────────────┤
│ > Type to search history (:red for duds, X to delete filtered, ? Help) │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Under the Hood: For Engineers & AI Agents

### 1. PSReadLine History Storage Semantics
PowerShell's PSReadLine module writes command history to:
`$env:APPDATA\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt`

- **Single-Line Commands**: Written as plain text lines separated by standard CRLF/LF.
- **Multi-Line Commands**: Written with trailing backticks (`` ` ``) at the end of each line as a continuation token, terminated by the closing line without a backtick.
- **Rendering Artifacts**: When PSReadLine encounters deep multi-line blocks or malformed escape sequences during console history cycling, its internal buffer coordinate calculations break relative to Windows Terminal / ConHost viewports.
- **Persistence Sync**: This tool directly manipulates and rewrites `ConsoleHost_history.txt` using strict UTF-8 (`utf-8` without BOM) to ensure 100% compatibility with PSReadLine without file corruption.

### 2. Dud & Syntax Error Classifier (State Machine)
Rather than executing untrusted past commands in a live shell, the TUI runs a deterministic lexical analysis state machine (`is_dud_command`):
1. **Traceback & Error Scraping**: Detects PowerShell error headers (`+ CategoryInfo`, `+ FullyQualifiedErrorId`, `At line:`, `: The term '...' is not recognized`).
2. **Caret & Underline Artifacts**: Matches copied CLI diagnostic indicators (`^^^^^`, `+ ~~~~~~`).
3. **Leading Punctuation Faults**: Flags commands starting with invalid leading delimiters (`;`, `|`, `,`, `}`, `)`).
4. **Balanced Delimiter & Quote Lexer**: Tracks single quotes (`'`), double quotes (`"`), PowerShell backtick escapes (`` ` ``), and nested bracket stacks (`()`, `[]`, `{}`) while respecting quote isolation (e.g., `'` inside `""` is treated as literal text).

### 3. Non-Blocking Editor Dispatch
When launching editors (such as Sublime Text or `$env:EDITOR`), the tool parses arguments with `shlex.split`, removes blocking flags (`--wait` / `-w`), and checks standard installation directories before starting the process with `subprocess.Popen`.

---

## 🚀 Quickstart & Installation

### Prerequisites
- Python 3.10 or higher
- PowerShell 5.1 / PowerShell 7+ on Windows

### 1. Clone the Repository
```powershell
git clone https://github.com/eloqven/powershell-history-navigator.git
cd powershell-history-navigator
```

### 2. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 3. Run the Navigator
```powershell
python history_tui.py
```
*(or execute `./run_history_tui.ps1`)*

---

## Add a Global `hist` Command in PowerShell

Add a quick alias to your PowerShell `$PROFILE` so you can launch the navigator from any terminal window by typing `hist`:

```powershell
if (!(Test-Path $PROFILE)) { New-Item -Path $PROFILE -ItemType File -Force }
Add-Content $PROFILE @"

function hist { python "D:\powershell-history-navigator\history_tui.py" }
"@
```

---

## Interface Preview (with Shortcut Keys Modal)

<div align="center">

<img src="./assets/screenshot.png" alt="PowerShell History Navigator - TUI Interface with Keyboard Shortcut Modal" width="900" style="border-radius: 12px; border: 1px solid #444; box-shadow: 0 8px 24px rgba(0,0,0,0.5); margin: 16px 0;"/>

*Press `?`, `H`, or `F1` at any time inside the TUI to toggle the on-screen shortcut cheatsheet.*

</div>

---

## 📖 How to Use & Workflow Guide

### 1. Searching & Instant Navigation
- **Live Search**: Press **`/`** to jump to the search bar. As you type, the table updates in real-time.
- **Seamless Arrow Keys**: Press **`↑`** or **`↓`** at any moment — even while actively typing in the search box — to immediately highlight and navigate through matching commands.
- **Clear Search**: Press **`Esc`** to clear your search query and return focus to the command table.

---

### 2. Vim-Style Command Mode (`:`)
Press **`:`** (or `Shift + ;`) from anywhere in the app to enter **Command Mode**. The bottom bar automatically opens with `:` ready for you to execute 1-word commands:

- **`:red`** or **`:duds`** — Isolate and filter only broken syntax / dud commands.
- **`:edit`** or **`:mod`** — Open the in-place editor for the highlighted command.
- **`:sort`** or **`:invert`** — Flip history sorting order between Newest-First and Oldest-First.
- **`:theme`** — Cycle through color palettes (*or jump directly with `:monokai`*, *`:dracula`*, *`:tokyo`*).
- **`:del`** — Delete the currently highlighted command from history.
- **`:purge`** or **`:clean`** — Delete all currently filtered commands (with double confirmation).
- **`:subl`** or **`:open`** — Open your history file in Sublime Text or your default text editor.
- **`:reload`** or **`:sync`** — Re-read history from disk while preserving your current search filter.
- **`:help`** or **`:keys`** — Open the on-screen shortcut cheat-sheet.
- **`:q`** or **`:quit`** — Exit the application.

---

### 3. In-Place Command Editing (`M` or `:edit`)
Found a useful past command with a small typo, outdated branch name, or wrong path?
1. Highlight the command in the list and press **`M`** (or **`I`**, or type `:edit`).
2. An interactive editing window pops up pre-loaded with the full command.
3. Edit the command text using arrow keys and backspace.
4. Press **`Enter`** (or click **Save to Disk**) to update the command in `ConsoleHost_history.txt` on disk, or press **`Ctrl + C`** to copy the modified version directly to your clipboard and exit.

---

### 4. Finding & Purging Syntax Errors & Duds (`:red` -> `X`)
Accidentally pasted CLI error output, multiline stack traces, or unbalanced strings into your terminal?
1. Type **`:red`** (or **`:duds`**) in the bottom bar. The table immediately filters to show **only** problematic commands flagged with red indicators (`[!]` and `[Syntax Error]`).
2. To delete a single dud, press **`Delete`** or **`D`**.
3. To delete **ALL matching duds at once**:
   - Press **`X`** (or **`Shift + Delete`**, or type `:purge`).
   - Pass through the two-step safety confirmation modals (`Enter` -> `Enter`).
   - All bad commands are permanently wiped from your history file on disk!

---

### 5. Custom Sorting & Classic Terminal Mode (`S` or `:sort`)
Press **`S`** to toggle between two distinct navigation paradigms:
- **Newest First (Default)**: Your most recent commands are at Row #1 (Top), allowing you to review recent work from top to bottom.
- **Classic Terminal Mode (Oldest First)**: Mirrors standard terminal prompt history where oldest commands are at the top and the newest command is preselected at the very bottom (Row #N).

---

### 6. Full-TUI Theme Immersion (`T` or `:theme`)
Press **`T`** to cycle between three themes that transform the entire layout (screen background, table headers, cursor highlight colors, preview borders, and PowerShell syntax highlighting):
- **Monokai**: `#272822` dark background with green headers and magenta accents.
- **Dracula**: `#282a36` purple background with cyan headers and pink borders.
- **Tokyo Night**: `#1a1b26` dark blue background with indigo headers and blue borders.

---

### 7. Sublime Text & External Editor Integration (`E` / `R`)
- Press **`E`** (or **`O`**, or `:subl`) to open `ConsoleHost_history.txt` directly in Sublime Text or your configured `$env:EDITOR`.
- Edit, clean, or reorganize your history manually in your editor and save.
- Switch back to the TUI and press **`R`** (or `:reload`) to sync the changes immediately. Any active search query is preserved automatically.

---

## Keyboard Shortcuts & Command Mode

| Key | Colon Command | Action | Description |
|:---|:---|:---|:---|
| `↑` / `↓` | — | **Navigate** | Move through commands (works directly from search bar too) |
| `←` / `→` | — | **Jump Page** | Jump 10 items backward / forward |
| `:` | — | **Command Mode** | Focus bottom bar and insert `:` |
| `/` | — | **Focus Search** | Focus live search input box |
| `Esc` | — | **Clear / Unfocus** | Clear search input or return focus to history table |
| — | `:red` / `:duds` | **Dud Filter** | Filter and isolate **only** bad syntax / error commands |
| `Enter` | `:copy` / `:c` | **Copy & Exit** | Copy selected command to clipboard and exit TUI |
| `C` | — | **Copy Only** | Copy selected command without closing TUI |
| `M` / `I` | `:edit` / `:mod` | **In-Place Edit** | Open interactive editor to modify command in-place |
| `Delete` / `D` | `:del` / `:delete` | **Delete Single** | Permanently delete selected command from history |
| `X` / `Shift+Del` | `:purge` / `:clean` | **Bulk Delete** | Delete **all filtered commands** (requires 2 confirmations) |
| `S` | `:sort` / `:invert` | **Toggle Sort** | Flip sorting order (Newest First <-> Oldest First) |
| `T` | `:theme` | **Toggle Theme** | Cycle themes (**Monokai** <-> **Dracula** <-> **Tokyo Night**) |
| `E` / `O` | `:subl` / `:open` | **Open in Editor** | Open `ConsoleHost_history.txt` in Sublime Text / Editor |
| `R` | `:reload` / `:sync`| **Reload** | Re-read history file from disk to sync new commands |
| `?` / `H` / `F1` | `:help` / `:keys` | **Help Overlay** | Open on-screen keybinding cheat-sheet |
| `Q` | `:q` / `:quit` | **Quit** | Close the application |

---

## Safety & Data Integrity

- **Automatic Backups**: Modifying or cleaning history writes safely to `ConsoleHost_history.txt`.
- **Bulk Deletion Safeguard**: The bulk delete command (`X` / `:purge`) is strictly blocked when all commands are visible, preventing accidental full wipes.
- **Double Confirmation**: Any batch deletion requires explicitly passing through two confirmation modals before touching disk storage.

---

## License

This project is licensed under the [MIT License](./LICENSE).
