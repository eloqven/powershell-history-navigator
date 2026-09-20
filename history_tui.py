import os
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import List, Optional

from rich.syntax import Syntax
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Input, DataTable, Static, Button
from textual.binding import Binding
from textual.reactive import reactive

SUBL_CANDIDATES = (
    r"C:\Program Files\Sublime Text 3\subl.exe",
    r"C:\Program Files\Sublime Text\subl.exe",
    r"C:\Program Files\Sublime Text 3\sublime_text.exe",
    r"C:\Program Files\Sublime Text\sublime_text.exe",
    r"C:\Program Files (x86)\Sublime Text 3\subl.exe",
)

BRACKETS = {"(": ")", "[": "]", "{": "}"}
CLOSING_BRACKETS = {")", "]", "}"}

def get_history_file_path() -> Path:
    app_data = os.environ.get("APPDATA", "")
    paths = []
    if app_data:
        paths.extend([
            Path(app_data) / "Microsoft" / "Windows" / "PowerShell" / "PSReadLine" / "ConsoleHost_history.txt",
            Path(app_data) / "Microsoft" / "PowerShell" / "PSReadLine" / "ConsoleHost_history.txt",
        ])
    # Cross-platform fallback (macOS / Linux PowerShell Core)
    home = Path.home()
    paths.extend([
        home / ".local" / "share" / "powershell" / "PSReadLine" / "ConsoleHost_history.txt",
        home / ".config" / "powershell" / "PSReadLine" / "ConsoleHost_history.txt",
    ])
    for p in paths:
        if p.exists():
            return p
    return paths[0] if paths else Path("ConsoleHost_history.txt")

def copy_to_clipboard(text: str) -> bool:
    candidates = [
        ("clip", ["clip"], "utf-16le"),
        ("pbcopy", ["pbcopy"], "utf-8"),
        ("wl-copy", ["wl-copy"], "utf-8"),
        ("xclip", ["xclip", "-selection", "clipboard"], "utf-8"),
    ]
    for binary, cmd, encoding in candidates:
        if shutil.which(binary):
            try:
                subprocess.run(cmd, input=text.encode(encoding), check=True)
                return True
            except Exception:
                return False
    return False

def is_dud_command(cmd: str) -> bool:
    """Detects if a history entry is a syntax dud, error traceback paste, or accidental input."""
    c = cmd.strip()
    if not c:
        return True

    # 1. Error traceback copy-pastes & caret/tilde error indicators
    if c.startswith(("+ ", "+~", "+^", "+ `", "At line:", "At C:", "+ CategoryInfo", "+ FullyQualifiedErrorId")):
        return True
    if "FullyQualifiedErrorId" in c or "CategoryInfo" in c or "CommandNotFoundException" in c:
        return True
    if re.search(r":\s*The term\s+['\"].*?['\"]\s+is not recognized", c):
        return True
    if "that the path is correct and try again" in c or "script file, or operable program" in c:
        return True
    if re.match(r"^[\+~^\.]{2,}", c):
        return True

    # 2. Starting with invalid leading punctuation (broken pipes / dangling brackets)
    if c.startswith(("}", ")", "]", ",", ";", "|")):
        return True

    # 3. State machine for unclosed quotes and unmatched brackets
    stack = []
    in_single = False
    in_double = False
    escaped = False

    for ch in c:
        if escaped:
            escaped = False
            continue

        if ch == "`":
            escaped = True
            continue

        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if ch in BRACKETS:
                stack.append(ch)
            elif ch in CLOSING_BRACKETS:
                if not stack or BRACKETS[stack.pop()] != ch:
                    return True

    if in_single or in_double or stack:
        return True

    return False

class SearchInput(Input):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, select_on_focus=False, **kwargs)

    BINDINGS = [
        Binding("up", "app.nav_up", "Up", show=False),
        Binding("down", "app.nav_down", "Down", show=False),
        Binding("escape", "app.clear_or_blur", "Cancel", show=False),
    ]

class EditCommandModal(ModalScreen[Optional[str]]):
    """In-place command editing modal."""
    CSS = """
    EditCommandModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.85);
    }

    #edit_dialog {
        width: 82;
        height: auto;
        max-height: 85%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    #edit_title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
        text-align: center;
    }

    #edit_input {
        width: 100%;
        height: auto;
        min-height: 3;
        max-height: 8;
        border: round $primary;
        margin-bottom: 1;
        background: $panel;
        color: $text;
    }

    #edit_buttons {
        align: center middle;
        height: auto;
        margin-top: 1;
    }

    #edit_buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel_edit", "Cancel", show=False),
        Binding("ctrl+s", "save_edit", "Save", show=False),
    ]

    def __init__(self, index: int, command: str):
        super().__init__()
        self.command_index = index
        self.original_command = command

    def compose(self) -> ComposeResult:
        with Vertical(id="edit_dialog"):
            yield Static(f"✏️ In-Place Edit Command #{self.command_index}", id="edit_title")
            yield Input(value=self.original_command, id="edit_input")
            with Horizontal(id="edit_buttons"):
                yield Button("Save to Disk (Enter)", id="btn_save", variant="success")
                yield Button("Copy & Exit (Ctrl+C)", id="btn_copy", variant="primary")
                yield Button("Cancel (Esc)", id="btn_cancel", variant="default")

    def on_mount(self) -> None:
        inp = self.query_one("#edit_input", Input)
        inp.focus()
        inp.cursor_position = len(inp.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        inp = self.query_one("#edit_input", Input)
        if event.button.id == "btn_save":
            self.dismiss(inp.value)
        elif event.button.id == "btn_copy":
            copy_to_clipboard(inp.value)
            self.app.exit(result=inp.value)
        else:
            self.dismiss(None)

    def action_save_edit(self) -> None:
        inp = self.query_one("#edit_input", Input)
        self.dismiss(inp.value)

    def action_cancel_edit(self) -> None:
        self.dismiss(None)

class ConfirmModal(ModalScreen[bool]):
    """Generic double-confirmation modal with customizable warning theme."""
    CSS = """
    ConfirmModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.8);
    }

    #confirm_dialog {
        width: 66;
        height: auto;
        border: thick #f92672;
        background: #1e1f1c;
        padding: 1 2;
    }

    #confirm_title {
        text-style: bold;
        text-align: center;
        color: #f92672;
        margin-bottom: 1;
    }

    #confirm_message {
        text-align: center;
        color: #f8f8f2;
        margin-bottom: 1;
    }

    #button_row {
        align: center middle;
        height: auto;
        margin-top: 1;
    }

    #button_row Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel_dialog", "Cancel", show=False),
        Binding("n", "cancel_dialog", "No", show=False),
        Binding("y", "confirm_dialog", "Yes", show=False),
    ]

    def __init__(self, title: str, message: str, confirm_label: str = "Yes, Continue", cancel_label: str = "Cancel (Esc)", is_final: bool = False):
        super().__init__()
        self.dialog_title = title
        self.dialog_message = message
        self.confirm_label = confirm_label
        self.cancel_label = cancel_label
        self.is_final = is_final

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm_dialog"):
            yield Static(self.dialog_title, id="confirm_title")
            yield Static(self.dialog_message, id="confirm_message")
            with Horizontal(id="button_row"):
                yield Button(self.confirm_label, id="btn_confirm", variant="error" if self.is_final else "warning")
                yield Button(self.cancel_label, id="btn_cancel", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#btn_confirm", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_cancel_dialog(self) -> None:
        self.dismiss(False)

    def action_confirm_dialog(self) -> None:
        self.dismiss(True)

class HelpModal(ModalScreen):
    """Modal popup screen showing all shortcuts and colon commands."""
    CSS = """
    HelpModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.8);
    }

    #help_container {
        width: 80;
        height: auto;
        max-height: 92%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    #help_title {
        text-style: bold;
        text-align: center;
        color: $accent;
        margin-bottom: 1;
    }

    #help_body {
        margin-bottom: 1;
    }

    #help_footer {
        text-align: center;
        color: $text-muted;
    }

    Screen.theme-monokai #help_container {
        border: thick #a6e22e;
        background: #1e1f1c;
    }
    Screen.theme-monokai #help_title {
        color: #fd971f;
    }

    Screen.theme-dracula #help_container {
        border: thick #bd93f9;
        background: #1e1f29;
    }
    Screen.theme-dracula #help_title {
        color: #ff79c6;
    }

    Screen.theme-tokyonight #help_container {
        border: thick #7aa2f7;
        background: #16161e;
    }
    Screen.theme-tokyonight #help_title {
        color: #bb9af7;
    }
    """

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Close"),
        Binding("question_mark", "app.pop_screen", "Close"),
        Binding("h", "app.pop_screen", "Close"),
        Binding("f1", "app.pop_screen", "Close"),
        Binding("enter", "app.pop_screen", "Close"),
        Binding("q", "app.pop_screen", "Close"),
        Binding("t", "app.toggle_theme", "Theme (T)"),
        Binding("r", "reload_from_modal", "Reload (R)"),
    ]

    def action_reload_from_modal(self) -> None:
        self.dismiss()
        if hasattr(self.app, "action_reload_history"):
            self.app.action_reload_history()

    def compose(self) -> ComposeResult:
        with Vertical(id="help_container"):
            yield Static("PowerShell History Navigator - Shortcuts & Commands", id="help_title")
            help_content = (
                "[bold cyan]Navigation & Search[/]\n"
                "  [yellow]↑ / ↓[/]            Navigate history rows (works from search bar)\n"
                "  [yellow]← / →[/]            Jump 10 items backward / forward\n"
                "  [yellow]/[/]                Focus live search bar\n"
                "  [yellow]Esc[/]              Clear search / Return to table\n\n"
                "[bold cyan]Actions & Colon Command Counterparts[/]\n"
                "  [yellow]Enter[/]            Copy & Exit                     [dim](:copy / :c)[/]\n"
                "  [yellow]M / I[/]            [bold green]In-Place Edit Command[/]           [dim](:edit / :mod)[/]\n"
                "  [yellow]Delete / D[/]       Delete selected command         [dim](:del / :delete)[/]\n"
                "  [bold red]X / Shift+Del[/]      [bold red]Delete ALL filtered commands[/]    [dim](:purge / :clean)[/]\n"
                "  [yellow]S[/]                Toggle Sort (Newest <-> Oldest) [dim](:sort / :invert)[/]\n"
                "  [yellow]T[/]                Toggle Theme (Monokai/Dracula)  [dim](:theme / :tokyo)[/]\n"
                "  [yellow]E / O[/]            Open in Sublime Text / Editor   [dim](:subl / :open)[/]\n"
                "  [yellow]R[/]                Reload history from disk        [dim](:reload / :sync)[/]\n"
                "  [yellow]? / H / F1[/]       Show this cheat-sheet           [dim](:help / :keys)[/]\n"
                "  [yellow]Q[/]                Quit                            [dim](:q / :quit)[/]\n\n"
                "[bold cyan]Special Filters[/]\n"
                "  [bold red]:red[/], [bold red]:duds[/]        Filter [bold red]ONLY bad syntax & error commands[/]\n"
            )
            yield Static(help_content, id="help_body")
            yield Static("Press [bold yellow]Esc[/], [bold yellow]?[/], or [bold yellow]Enter[/] to close", id="help_footer")

class HistoryDashboard(App):
    TITLE = "PowerShell History Navigator"
    SUB_TITLE = "Browse, Search, Copy & Clean History"

    THEMES = ["monokai", "dracula", "tokyonight"]
    current_theme_idx: int = reactive(0)
    sort_newest_first: bool = reactive(True)

    CSS = """
    Screen {
        background: #272822;
        color: #f8f8f2;
        overflow-x: hidden;
    }

    /* === Monokai Theme (Full Immersion) === */
    Screen.theme-monokai {
        background: #272822;
        color: #f8f8f2;
    }
    Screen.theme-monokai #preview_container {
        border: round #a6e22e;
        background: #1e1f1c;
    }
    Screen.theme-monokai #preview_title {
        color: #fd971f;
    }
    Screen.theme-monokai #history_table {
        border: round #66d9ef;
        background: #272822;
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
    Screen.theme-monokai #search_input {
        border: round #f92672;
        background: #1e1f1c;
        color: #f8f8f2;
    }
    Screen.theme-monokai #search_input:focus {
        border: double #a6e22e;
    }

    /* === Dracula Theme (Full Immersion) === */
    Screen.theme-dracula {
        background: #282a36;
        color: #f8f8f2;
    }
    Screen.theme-dracula #preview_container {
        border: round #bd93f9;
        background: #1e1f29;
    }
    Screen.theme-dracula #preview_title {
        color: #ff79c6;
    }
    Screen.theme-dracula #history_table {
        border: round #8be9fd;
        background: #282a36;
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
    Screen.theme-dracula #search_input {
        border: round #ff79c6;
        background: #1e1f29;
        color: #f8f8f2;
    }
    Screen.theme-dracula #search_input:focus {
        border: double #50fa7b;
    }

    /* === Tokyo Night Theme (Full Immersion) === */
    Screen.theme-tokyonight {
        background: #1a1b26;
        color: #c0caf5;
    }
    Screen.theme-tokyonight #preview_container {
        border: round #7aa2f7;
        background: #16161e;
    }
    Screen.theme-tokyonight #preview_title {
        color: #bb9af7;
    }
    Screen.theme-tokyonight #history_table {
        border: round #7dcfff;
        background: #1a1b26;
    }
    Screen.theme-tokyonight DataTable > .datatable--header {
        background: #16161e;
        color: #7aa2f7;
        text-style: bold;
    }
    Screen.theme-tokyonight DataTable > .datatable--cursor {
        background: #292e42;
        color: #7dcfff;
        text-style: bold;
    }
    Screen.theme-tokyonight #search_input {
        border: round #bb9af7;
        background: #16161e;
        color: #c0caf5;
    }
    Screen.theme-tokyonight #search_input:focus {
        border: double #7aa2f7;
    }

    #main_container {
        height: 1fr;
        padding: 0 1;
        overflow-x: hidden;
    }

    #preview_container {
        height: 32%;
        padding: 0 1;
        margin-top: 0;
        margin-bottom: 0;
        overflow-x: hidden;
    }

    #preview_title {
        text-style: bold;
        padding-bottom: 0;
    }

    #preview_text {
        height: 1fr;
        overflow-y: auto;
        overflow-x: hidden;
    }

    #history_table {
        height: 68%;
        margin-top: 0;
        overflow-x: hidden;
    }

    #search_box {
        dock: bottom;
        padding: 0 1;
        margin-top: 0;
        margin-bottom: 0;
        height: auto;
        overflow-x: hidden;
    }

    #search_input {
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("slash", "focus_search", "Search (/)"),
        Binding("colon", "focus_colon_search", "Command Mode (:)"),
        Binding("escape", "clear_or_blur", "Back / Clear"),
        Binding("up", "nav_up", "Up", show=False),
        Binding("down", "nav_down", "Down", show=False),
        Binding("delete", "delete_command", "Delete"),
        Binding("d", "delete_command", "Delete (D)"),
        Binding("m", "edit_command", "In-Place Edit (M)"),
        Binding("i", "edit_command", "Edit (I)", show=False),
        Binding("s", "toggle_sort_order", "Sort Order (S)"),
        Binding("x", "delete_filtered", "Delete Filtered (X)"),
        Binding("shift+delete", "delete_filtered", "Delete Filtered", show=False),
        Binding("enter", "copy_command", "Copy & Exit"),
        Binding("c", "copy_command_only", "Copy (C)"),
        Binding("e", "open_in_editor", "Edit File (E)"),
        Binding("o", "open_in_editor", "Open (O)", show=False),
        Binding("t", "toggle_theme", "Theme (T)"),
        Binding("r", "reload_history", "Reload (R)"),
        Binding("question_mark", "show_help", "Help (?)"),
        Binding("h", "show_help", "Help (H)", show=False),
        Binding("f1", "show_help", "Help (F1)", show=False),
        Binding("left", "cursor_left", "Left", show=False),
        Binding("right", "cursor_right", "Right", show=False),
        Binding("q", "quit", "Quit"),
    ]

    history_path: Path = get_history_file_path()
    all_commands: List[str] = reactive([])
    dud_flags: List[bool] = reactive([])
    filtered_indices: List[int] = reactive([])
    status_msg = reactive("Ready")
    _last_delete_time: float = 0.0

    def compose(self) -> ComposeResult:
        with Vertical(id="main_container"):
            with Vertical(id="preview_container"):
                yield Static("Command Preview", id="preview_title")
                yield Static("", id="preview_text")
            yield DataTable(id="history_table", cursor_type="row")
        with Vertical(id="search_box"):
            yield SearchInput(placeholder="Type : for commands (:help, :red, :edit, :sort, :theme, :q) or search...", id="search_input")

    def on_mount(self) -> None:
        table = self.query_one("#history_table", DataTable)
        table.add_columns("#", "Len", "Command")
        self.apply_theme_classes()
        self.load_history()
        table.focus()

    def apply_theme_classes(self) -> None:
        theme = self.THEMES[self.current_theme_idx]
        theme_classes = tuple(f"theme-{t}" for t in self.THEMES)
        screens = [*getattr(self, "screen_stack", []), self.screen]
        for scr in dict.fromkeys(screens):
            scr.remove_class(*theme_classes)
            scr.add_class(f"theme-{theme}")

    def action_toggle_theme(self) -> None:
        next_theme = self.THEMES[(self.current_theme_idx + 1) % len(self.THEMES)]
        self.set_theme_by_name(next_theme)

    def set_theme_by_name(self, name: str) -> None:
        name_clean = name.lower().replace(" ", "").replace("-", "")
        if "mono" in name_clean:
            self.current_theme_idx = 0
        elif "drac" in name_clean:
            self.current_theme_idx = 1
        elif "tokyo" in name_clean or "night" in name_clean:
            self.current_theme_idx = 2
        else:
            self.notify("Available themes: :monokai, :dracula, :tokyonight", timeout=2.5)
            return
        self.apply_theme_classes()
        theme_name = self.THEMES[self.current_theme_idx].replace("tokyonight", "Tokyo Night").title()
        self.notify(f"Theme Palette: {theme_name} 🎨", timeout=2.0)
        table = self.query_one("#history_table", DataTable)
        self.update_preview_for_row(table.cursor_row)

    def action_toggle_sort_order(self) -> None:
        self.sort_newest_first = not self.sort_newest_first
        mode = "Newest at Top (Reverse-Chronological)" if self.sort_newest_first else "Newest at Bottom (Classic Terminal)"
        self.notify(f"Sort Order: {mode} 🔃", timeout=2.5)
        search_val = self.query_one("#search_input", SearchInput).value
        self.apply_filter(search_val)

    def action_show_help(self) -> None:
        self.push_screen(HelpModal())

    def watch_status_msg(self, msg: str) -> None:
        if msg and msg != "Ready":
            try:
                self.notify(msg, timeout=2.5)
            except Exception:
                pass

    def load_history(self, preserve_filter: bool = True) -> None:
        try:
            with open(self.history_path, "r", encoding="utf-8", errors="replace") as f:
                lines = [line.rstrip("\r\n") for line in f]
            self.all_commands = lines
            self.dud_flags = [is_dud_command(cmd) for cmd in self.all_commands]
            dud_count = sum(1 for is_d in self.dud_flags if is_d)
            self.status_msg = f"Loaded {len(self.all_commands)} commands ({dud_count} syntax duds)"
        except FileNotFoundError:
            self.all_commands = []
            self.dud_flags = []
            self.status_msg = f"History file not found: {self.history_path}"
        except Exception as e:
            self.all_commands = []
            self.dud_flags = []
            self.status_msg = f"Error loading file: {e}"

        current_query = ""
        if preserve_filter:
            try:
                search_input = self.query_one("#search_input", SearchInput)
                current_query = search_input.value
            except Exception:
                current_query = ""

        self.apply_filter(current_query)

    def apply_filter(self, query: str) -> None:
        q = query.strip().lower()
        filter_duds_only = False

        # Support :red, :duds, :err, :error, :bad tags
        dud_triggers = [":red", ":duds", ":dud", ":err", ":error", ":bad"]
        matched_trigger = next((t for t in dud_triggers if q == t or q.startswith(t + " ")), None)
        if matched_trigger:
            filter_duds_only = True
            q = q[len(matched_trigger):].strip()

        total = len(self.all_commands)
        indices = []

        if self.sort_newest_first:
            range_iter = range(total - 1, -1, -1)
        else:
            range_iter = range(0, total)

        for i in range_iter:
            cmd = self.all_commands[i]
            is_dud = self.dud_flags[i] if i < len(self.dud_flags) else False

            if filter_duds_only and not is_dud:
                continue
            if q and q not in cmd.lower():
                continue
            indices.append(i)

        self.filtered_indices = indices
        self.refresh_table()

    def format_command_cell(self, cmd: str, is_dud: bool) -> Text:
        """Adds colored syntax styling to command rows, highlighting duds in bold red."""
        display_cmd = cmd.replace("\t", " ").replace("\n", " ⏎ ")
        text = Text()
        if is_dud:
            text.append("[!] ", style="bold bright_red")
            text.append(display_cmd, style="bold red")
        else:
            parts = display_cmd.split(" ", 1)
            if parts:
                text.append(parts[0], style="bold cyan")
                if len(parts) > 1:
                    text.append(" " + parts[1], style="default")
            else:
                text.append(display_cmd)
        return text

    def refresh_table(self) -> None:
        table = self.query_one("#history_table", DataTable)
        current_row = table.cursor_row
        table.clear()

        rows = []
        for real_idx in self.filtered_indices:
            cmd = self.all_commands[real_idx]
            is_dud = self.dud_flags[real_idx] if real_idx < len(self.dud_flags) else False
            styled_cmd = self.format_command_cell(cmd, is_dud)
            idx_style = "bold red" if is_dud else "bold yellow"
            len_style = "red" if is_dud else "magenta"
            rows.append((
                Text(str(real_idx + 1), style=idx_style),
                Text(str(len(cmd)), style=len_style),
                styled_cmd,
            ))
        table.add_rows(rows)

        if len(self.filtered_indices) > 0:
            if not self.sort_newest_first and (current_row is None or current_row == 0):
                # In chronological mode, preselect and scroll to the bottom row
                new_row = len(self.filtered_indices) - 1
            else:
                new_row = min(max(0, current_row if current_row is not None else 0), len(self.filtered_indices) - 1)
            table.move_cursor(row=new_row)
            self.update_preview_for_row(new_row)
        else:
            self.update_preview_text("No matching commands.")

    def on_input_changed(self, event: Input.Changed) -> None:
        self.apply_filter(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        val = event.value.strip()
        if val.startswith(":"):
            # Command Mode execution
            cmd_body = val[1:].strip().lower()
            cmd_parts = cmd_body.split()
            base_cmd = cmd_parts[0] if cmd_parts else ""

            if base_cmd in ("q", "quit", "exit"):
                self.exit()
            elif base_cmd in ("help", "keys", "?"):
                self.action_show_help()
            elif base_cmd in ("theme", "t"):
                if len(cmd_parts) > 1:
                    self.set_theme_by_name(cmd_parts[1])
                else:
                    self.action_toggle_theme()
            elif base_cmd in ("monokai", "dracula", "tokyonight", "tokyo"):
                self.set_theme_by_name(base_cmd)
            elif base_cmd in ("edit", "mod", "m"):
                self.action_edit_command()
            elif base_cmd in ("del", "delete", "d"):
                self.action_delete_command()
            elif base_cmd in ("purge", "clean", "x"):
                self.action_delete_filtered()
            elif base_cmd in ("sort", "invert", "s"):
                self.action_toggle_sort_order()
            elif base_cmd in ("subl", "code", "open", "e"):
                self.action_open_in_editor()
            elif base_cmd in ("reload", "refresh", "sync", "r"):
                self.action_reload_history()
            elif base_cmd in ("copy", "c"):
                self.action_copy_command()
            elif base_cmd in ("red", "duds", "dud", "err"):
                # Retain filter in search bar and focus table
                self.query_one("#history_table", DataTable).focus()
            else:
                self.notify(f"Unknown command: :{base_cmd} (Type :help for commands)", timeout=3.0)
        else:
            # Normal search submitted: transfer focus to table
            self.query_one("#history_table", DataTable).focus()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self.update_preview_for_row(event.cursor_row)

    def update_preview_for_row(self, row_idx: Optional[int]) -> None:
        if row_idx is not None and 0 <= row_idx < len(self.filtered_indices):
            real_idx = self.filtered_indices[row_idx]
            cmd = self.all_commands[real_idx]
            is_dud = self.dud_flags[real_idx] if real_idx < len(self.dud_flags) else False
            self.update_preview_text(cmd, real_idx + 1, len(cmd), is_dud)
        else:
            self.update_preview_text("")

    def update_preview_text(self, text: str, index: Optional[int] = None, length: Optional[int] = None, is_dud: bool = False) -> None:
        title = self.query_one("#preview_title", Static)
        body = self.query_one("#preview_text", Static)
        if index is not None:
            if is_dud:
                title.update(f"Command #{index} [bold red][Syntax Error][/] ({length} chars)")
                formatted_dud = Text(text, style="bold red")
                body.update(formatted_dud)
            else:
                title.update(f"Command #{index} ({length} chars)")
                theme = self.THEMES[self.current_theme_idx]
                syntax = Syntax(
                    text,
                    "powershell",
                    theme="monokai" if theme == "monokai" else "dracula",
                    line_numbers=False,
                    word_wrap=True,
                    background_color="default"
                )
                body.update(syntax)
        else:
            title.update("Command Preview")
            body.update(text)

    def action_focus_search(self) -> None:
        inp = self.query_one("#search_input", SearchInput)
        inp.focus()
        inp.cursor_position = len(inp.value)

    def action_focus_colon_search(self) -> None:
        """Command Mode: Focuses input bar and adds ':' character."""
        inp = self.query_one("#search_input", SearchInput)
        if not inp.value.startswith(":"):
            inp.value = ":" + inp.value
        self.action_focus_search()

    def action_clear_or_blur(self) -> None:
        inp = self.query_one("#search_input", SearchInput)
        table = self.query_one("#history_table", DataTable)
        if inp.has_focus:
            if inp.value:
                inp.value = ""
            else:
                table.focus()
        else:
            table.focus()

    def action_nav_up(self) -> None:
        table = self.query_one("#history_table", DataTable)
        if not table.has_focus:
            table.focus()
        if len(self.filtered_indices) == 0:
            return
        current = table.cursor_row if table.cursor_row is not None else 0
        new_row = max(0, current - 1)
        table.move_cursor(row=new_row)
        self.update_preview_for_row(new_row)

    def action_nav_down(self) -> None:
        table = self.query_one("#history_table", DataTable)
        if not table.has_focus:
            table.focus()
        if len(self.filtered_indices) == 0:
            return
        current = table.cursor_row if table.cursor_row is not None else 0
        new_row = min(len(self.filtered_indices) - 1, current + 1)
        table.move_cursor(row=new_row)
        self.update_preview_for_row(new_row)

    def action_cursor_left(self) -> None:
        table = self.query_one("#history_table", DataTable)
        if table.has_focus and table.cursor_row is not None:
            new_row = max(0, table.cursor_row - 10)
            table.move_cursor(row=new_row)
            self.update_preview_for_row(new_row)

    def action_cursor_right(self) -> None:
        table = self.query_one("#history_table", DataTable)
        if table.has_focus and table.cursor_row is not None:
            new_row = min(len(self.filtered_indices) - 1, table.cursor_row + 10)
            table.move_cursor(row=new_row)
            self.update_preview_for_row(new_row)

    def action_delete_command(self) -> None:
        search_input = self.query_one("#search_input", SearchInput)
        if search_input.has_focus:
            return

        now = time.time()
        if now - self._last_delete_time < 0.35:
            return
        self._last_delete_time = now

        table = self.query_one("#history_table", DataTable)
        row = table.cursor_row
        if row is None or row < 0 or row >= len(self.filtered_indices):
            return

        real_idx = self.filtered_indices[row]
        deleted_cmd = self.all_commands.pop(real_idx)
        if real_idx < len(self.dud_flags):
            self.dud_flags.pop(real_idx)

        self.save_history_to_file()
        self.status_msg = f"Deleted command #{real_idx + 1}: '{deleted_cmd[:40]}...'"

        search_val = search_input.value
        self.apply_filter(search_val)

    def action_edit_command(self) -> None:
        """Opens interactive modal to edit selected command in-place."""
        table = self.query_one("#history_table", DataTable)
        row = table.cursor_row
        if row is None or row < 0 or row >= len(self.filtered_indices):
            self.notify("Select a command to edit.", timeout=2.0)
            return

        real_idx = self.filtered_indices[row]
        current_cmd = self.all_commands[real_idx]

        def on_edit_result(new_command: Optional[str]) -> None:
            if new_command is None:
                return

            new_clean = new_command.strip()
            if not new_clean:
                self.notify("Edited command cannot be empty.", timeout=2.0)
                return

            self.all_commands[real_idx] = new_clean
            self.dud_flags[real_idx] = is_dud_command(new_clean)
            self.save_history_to_file()
            self.notify(f"Updated command #{real_idx + 1} on disk! 💾", timeout=2.5)

            search_val = self.query_one("#search_input", SearchInput).value
            self.apply_filter(search_val)

        self.push_screen(EditCommandModal(real_idx + 1, current_cmd), on_edit_result)

    def action_delete_filtered(self) -> None:
        """Batch delete all currently filtered commands (with safety check + double confirmation)."""
        search_input = self.query_one("#search_input", SearchInput)
        query = search_input.value.strip()

        if not query or len(self.filtered_indices) == len(self.all_commands):
            self.notify("⚠️ Safety Block: Bulk delete requires an active search filter!", timeout=3.5)
            return

        count_to_delete = len(self.filtered_indices)
        if count_to_delete == 0:
            self.notify("No filtered commands to delete.", timeout=2.0)
            return

        step1_title = "⚠️ Confirm Bulk Delete (Step 1 of 2)"
        step1_msg = (
            f"You are about to delete ALL [bold yellow]{count_to_delete}[/] commands\n"
            f"matching filter: [bold cyan]\"{query}\"[/]\n\n"
            "Do you want to proceed?"
        )

        def on_step1_result(confirmed: bool) -> None:
            if not confirmed:
                self.notify("Bulk delete cancelled.", timeout=2.0)
                return

            step2_title = "🚨 FINAL CONFIRMATION (Step 2 of 2)"
            step2_msg = (
                f"[bold red]PERMANENT ACTION:[/] This will permanently remove\n"
                f"[bold yellow]{count_to_delete}[/] commands from your history file on disk.\n\n"
                "Are you absolutely sure?"
            )

            def on_step2_result(final_confirmed: bool) -> None:
                if not final_confirmed:
                    self.notify("Bulk delete cancelled.", timeout=2.0)
                    return

                delete_set = set(self.filtered_indices)
                new_commands = []
                new_dud_flags = []
                for idx, cmd in enumerate(self.all_commands):
                    if idx not in delete_set:
                        new_commands.append(cmd)
                        new_dud_flags.append(self.dud_flags[idx])

                self.all_commands = new_commands
                self.dud_flags = new_dud_flags

                self.save_history_to_file()
                search_input.value = ""
                self.apply_filter("")
                self.notify(f"🗑️ Deleted {count_to_delete} commands from history!", timeout=3.5)

            self.push_screen(
                ConfirmModal(
                    title=step2_title,
                    message=step2_msg,
                    confirm_label="⚠️ Permanently Delete",
                    cancel_label="Cancel (Esc)",
                    is_final=True
                ),
                on_step2_result
            )

        self.push_screen(
            ConfirmModal(
                title=step1_title,
                message=step1_msg,
                confirm_label="Yes, Continue (Enter)",
                cancel_label="Cancel (Esc)",
                is_final=False
            ),
            on_step1_result
        )

    def save_history_to_file(self) -> None:
        try:
            with open(self.history_path, "w", encoding="utf-8", newline="\n") as f:
                for cmd in self.all_commands:
                    f.write(cmd + "\n")
        except Exception as e:
            self.status_msg = f"Error saving history: {e}"

    def action_copy_command(self) -> None:
        cmd = self.get_selected_command()
        if cmd:
            copy_to_clipboard(cmd)
            self.exit(result=cmd)

    def action_copy_command_only(self) -> None:
        cmd = self.get_selected_command()
        if cmd:
            copy_to_clipboard(cmd)
            self.status_msg = "Copied selected command to clipboard!"

    def action_open_in_editor(self) -> None:
        if not self.history_path.exists():
            self.status_msg = f"History file not found: {self.history_path}"
            return

        target_file = str(self.history_path)

        editor_env = os.environ.get("EDITOR") or os.environ.get("VISUAL")
        if editor_env:
            parts = shlex.split(editor_env, posix=False)
            if parts:
                exe_name = parts[0]
                flags = [arg for arg in parts[1:] if arg not in ("--wait", "-w")]
                resolved = shutil.which(exe_name)
                if not resolved:
                    for candidate in SUBL_CANDIDATES:
                        if os.path.exists(candidate):
                            resolved = candidate
                            break

                if resolved:
                    try:
                        subprocess.Popen([resolved, *flags, target_file])
                        self.status_msg = f"Opened history in {Path(resolved).name}"
                        return
                    except Exception:
                        pass

        for candidate in SUBL_CANDIDATES:
            if os.path.exists(candidate):
                try:
                    subprocess.Popen([candidate, target_file])
                    self.status_msg = "Opened history in Sublime Text"
                    return
                except Exception:
                    continue

        try:
            os.startfile(target_file)
            self.status_msg = "Opened history in default editor"
            return
        except Exception:
            pass

        try:
            subprocess.Popen(["notepad.exe", target_file])
            self.status_msg = "Opened history in Notepad"
        except Exception as e:
            self.status_msg = f"Error opening editor: {e}"

    def action_reload_history(self) -> None:
        try:
            table = self.query_one("#history_table", DataTable)
            preview = self.query_one("#preview_container", Vertical)
            table.styles.animate("opacity", value=0.35, duration=0.08, on_complete=lambda: table.styles.animate("opacity", value=1.0, duration=0.14))
            preview.styles.animate("opacity", value=0.45, duration=0.08, on_complete=lambda: preview.styles.animate("opacity", value=1.0, duration=0.14))
        except Exception:
            pass

        self.load_history(preserve_filter=True)
        self.notify(f"Synced {len(self.all_commands)} commands from disk ⚡", timeout=2.0)

    def get_selected_command(self) -> Optional[str]:
        table = self.query_one("#history_table", DataTable)
        row = table.cursor_row
        if row is not None and 0 <= row < len(self.filtered_indices):
            real_idx = self.filtered_indices[row]
            return self.all_commands[real_idx]
        return None

def main() -> None:
    app = HistoryDashboard()
    app.run()

if __name__ == "__main__":
    main()