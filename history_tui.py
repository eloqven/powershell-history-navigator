import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from rich.syntax import Syntax
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Header, Footer, Input, DataTable, Static, Button
from textual.binding import Binding
from textual.reactive import reactive

def get_history_file_path() -> Path:
    app_data = os.environ.get("APPDATA", "")
    paths = [
        Path(app_data) / "Microsoft" / "Windows" / "PowerShell" / "PSReadLine" / "ConsoleHost_history.txt",
        Path(app_data) / "Microsoft" / "PowerShell" / "PSReadLine" / "ConsoleHost_history.txt",
    ]
    for p in paths:
        if p.exists():
            return p
    return paths[0]

def copy_to_clipboard(text: str) -> bool:
    try:
        proc = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=True)
        proc.communicate(input=text.encode("utf-16le"))
        return True
    except Exception:
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
    brackets = {"(": ")", "[": "]", "{": "}"}
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
            if ch in brackets:
                stack.append(ch)
            elif ch in brackets.values():
                if not stack or brackets[stack.pop()] != ch:
                    return True

    if in_single or in_double or stack:
        return True

    return False

class SearchInput(Input):
    BINDINGS = [
        Binding("up", "app.nav_up", "Up", show=False),
        Binding("down", "app.nav_down", "Down", show=False),
        Binding("escape", "app.clear_or_blur", "Cancel", show=False),
    ]

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
    """Modal popup screen showing all shortcuts and commands."""
    CSS = """
    HelpModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.75);
    }

    #help_container {
        width: 76;
        height: auto;
        max-height: 90%;
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
    """

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Close"),
        Binding("question_mark", "app.pop_screen", "Close"),
        Binding("h", "app.pop_screen", "Close"),
        Binding("f1", "app.pop_screen", "Close"),
        Binding("enter", "app.pop_screen", "Close"),
        Binding("q", "app.pop_screen", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help_container"):
            yield Static("⚡ PowerShell History Navigator - Keyboard Shortcuts", id="help_title")
            help_content = (
                "[bold cyan]Navigation & Selection[/]\n"
                "  [yellow]↑ / ↓[/]            Navigate commands (works from search bar too!)\n"
                "  [yellow]← / →[/]            Jump 10 items backward / forward\n"
                "  [yellow]/[/]                Focus live search bar\n"
                "  [yellow]Esc[/]              Clear search / Return to table\n\n"
                "[bold cyan]Search Filters[/]\n"
                "  [bold red]:red:[/], [bold red]:red[/], [bold red]:err[/]     Filter [bold red]ONLY bad syntax / dud commands[/]\n\n"
                "[bold cyan]Actions[/]\n"
                "  [yellow]Enter[/]            Copy selected command to clipboard & exit\n"
                "  [yellow]C[/]                Copy selected command without exiting\n"
                "  [yellow]Delete / D[/]       Permanently delete selected command from history\n"
                "  [bold red]X / Shift+Del[/]      [bold red]Delete ALL filtered commands[/] (Requires filter + 2 confirmations)\n"
                "  [yellow]E / O[/]            Open history file in Sublime Text / Default Editor\n"
                "  [yellow]T[/]                Toggle Theme Palette ([bold magenta]Monokai[/] ⇄ [bold purple]Dracula[/])\n"
                "  [yellow]R[/]                Reload history from disk\n"
                "  [yellow]? / H / F1[/]       Show this help cheat-sheet\n"
                "  [yellow]Q[/]                Quit\n"
            )
            yield Static(help_content, id="help_body")
            yield Static("Press [bold yellow]Esc[/], [bold yellow]?[/], or [bold yellow]Enter[/] to close", id="help_footer")

class HistoryDashboard(App):
    TITLE = "PowerShell History Navigator"
    SUB_TITLE = "Browse, Search, Copy & Clean History (Newest First)"

    THEMES = ["monokai", "dracula"]
    current_theme_idx: int = reactive(0)

    CSS = """
    Screen {
        background: #272822;
        color: #f8f8f2;
        overflow-x: hidden;
    }

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

    Screen.theme-monokai #search_input {
        border: round #f92672;
        background: #1e1f1c;
        color: #f8f8f2;
    }

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

    Screen.theme-dracula #search_input {
        border: round #50fa7b;
        background: #1e1f29;
        color: #f8f8f2;
    }

    #main_container {
        height: 1fr;
        padding: 0 1;
        overflow-x: hidden;
    }

    #preview_container {
        height: 32%;
        padding: 0 1;
        margin-top: 1;
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
        Binding("escape", "clear_or_blur", "Back / Clear"),
        Binding("up", "nav_up", "Up", show=False),
        Binding("down", "nav_down", "Down", show=False),
        Binding("delete", "delete_command", "Delete"),
        Binding("d", "delete_command", "Delete (D)"),
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

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="main_container"):
            with Vertical(id="preview_container"):
                yield Static("Command Preview", id="preview_title")
                yield Static("", id="preview_text")
            yield DataTable(id="history_table", cursor_type="row")
        with Vertical(id="search_box"):
            yield SearchInput(placeholder="Search (:red: for duds, X to delete filtered, ? for Help)...", id="search_input")

    def on_mount(self) -> None:
        table = self.query_one("#history_table", DataTable)
        table.add_columns("#", "Len", "Command")
        self.apply_theme_classes()
        self.load_history()
        table.focus()

    def apply_theme_classes(self) -> None:
        theme = self.THEMES[self.current_theme_idx]
        self.screen.remove_class("theme-monokai")
        self.screen.remove_class("theme-dracula")
        self.screen.add_class(f"theme-{theme}")

    def action_toggle_theme(self) -> None:
        self.current_theme_idx = (self.current_theme_idx + 1) % len(self.THEMES)
        self.apply_theme_classes()
        theme_name = self.THEMES[self.current_theme_idx].title()
        self.notify(f"Theme Palette: {theme_name} 🎨", timeout=2.0)
        table = self.query_one("#history_table", DataTable)
        self.update_preview_for_row(table.cursor_row)

    def action_show_help(self) -> None:
        self.push_screen(HelpModal())

    def watch_status_msg(self, msg: str) -> None:
        if msg and msg != "Ready":
            try:
                self.notify(msg, timeout=2.5)
            except Exception:
                pass

    def load_history(self) -> None:
        if self.history_path.exists():
            try:
                with open(self.history_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = [line.rstrip("\r\n") for line in f.readlines()]
                self.all_commands = lines
                self.dud_flags = [is_dud_command(cmd) for cmd in self.all_commands]
                dud_count = sum(1 for is_d in self.dud_flags if is_d)
                self.status_msg = f"Loaded {len(self.all_commands)} commands ({dud_count} syntax duds)"
            except Exception as e:
                self.all_commands = []
                self.dud_flags = []
                self.status_msg = f"Error loading file: {e}"
        else:
            self.all_commands = []
            self.dud_flags = []
            self.status_msg = f"History file not found: {self.history_path}"

        self.apply_filter("")

    def apply_filter(self, query: str) -> None:
        q = query.strip().lower()
        filter_duds_only = False

        # Support :red:, :red, :err, :error, :bad, :dud tags
        dud_triggers = [":red:", ":red", ":err", ":error", ":bad", ":dud"]
        matched_trigger = next((t for t in dud_triggers if q.startswith(t)), None)
        if matched_trigger:
            filter_duds_only = True
            q = q[len(matched_trigger):].strip()

        total = len(self.all_commands)
        indices = []
        for i in range(total - 1, -1, -1):
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
            text.append("✖ ", style="bold bright_red")
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

        for display_idx, real_idx in enumerate(self.filtered_indices):
            cmd = self.all_commands[real_idx]
            is_dud = self.dud_flags[real_idx] if real_idx < len(self.dud_flags) else False
            styled_cmd = self.format_command_cell(cmd, is_dud)

            if is_dud:
                idx_style = "bold red"
                len_style = "red"
            else:
                idx_style = "bold yellow"
                len_style = "magenta"

            table.add_row(
                Text(str(real_idx + 1), style=idx_style),
                Text(str(len(cmd)), style=len_style),
                styled_cmd
            )

        if len(self.filtered_indices) > 0:
            new_row = min(max(0, current_row if current_row is not None else 0), len(self.filtered_indices) - 1)
            table.move_cursor(row=new_row)
            self.update_preview_for_row(new_row)
        else:
            self.update_preview_text("No matching commands.")

    def on_input_changed(self, event: Input.Changed) -> None:
        self.apply_filter(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
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
                title.update(f"[bold red]✖ Dud / Syntax Error Command #{index} ({length} chars)[/]")
                formatted_dud = Text(text, style="bold red")
                body.update(formatted_dud)
            else:
                title.update(f"Command #{index} ({length} chars)")
                theme = self.THEMES[self.current_theme_idx]
                syntax = Syntax(
                    text,
                    "powershell",
                    theme=theme,
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
        table = self.query_one("#history_table", DataTable)
        row = table.cursor_row
        if row is None or row < 0 or row >= len(self.filtered_indices):
            return

        real_idx = self.filtered_indices[row]
        deleted_cmd = self.all_commands.pop(real_idx)
        if real_idx < len(self.dud_flags):
            self.dud_flags.pop(real_idx)

        # Save to disk
        self.save_history_to_file()
        self.status_msg = f"Deleted command #{real_idx + 1}: '{deleted_cmd[:40]}...'"

        # Re-apply filter
        search_val = self.query_one("#search_input", SearchInput).value
        self.apply_filter(search_val)

    def action_delete_filtered(self) -> None:
        """Batch delete all currently filtered commands (with safety check + double confirmation)."""
        search_input = self.query_one("#search_input", SearchInput)
        query = search_input.value.strip()

        # 1. Safety check: must have active filter and not match entire unfiltered history
        if not query or len(self.filtered_indices) == len(self.all_commands):
            self.notify("⚠️ Safety Block: Bulk delete requires an active search filter!", timeout=3.5)
            return

        count_to_delete = len(self.filtered_indices)
        if count_to_delete == 0:
            self.notify("No filtered commands to delete.", timeout=2.0)
            return

        # 2. Step 1 Confirmation Modal
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

            # 3. Step 2 Final Confirmation Modal
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

                # Execute batch deletion
                delete_set = set(self.filtered_indices)
                new_commands = []
                new_dud_flags = []
                for idx, cmd in enumerate(self.all_commands):
                    if idx not in delete_set:
                        new_commands.append(cmd)
                        new_dud_flags.append(self.dud_flags[idx])

                self.all_commands = new_commands
                self.dud_flags = new_dud_flags

                # Save changes to disk
                self.save_history_to_file()

                # Reset search and refresh
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

        # 1. Parse EDITOR / VISUAL environment variables
        editor_env = os.environ.get("EDITOR") or os.environ.get("VISUAL")
        if editor_env:
            parts = shlex.split(editor_env, posix=False)
            if parts:
                exe_name = parts[0]
                flags = [arg for arg in parts[1:] if arg not in ("--wait", "-w")]
                resolved = shutil.which(exe_name)
                if not resolved:
                    for candidate in [
                        r"C:\Program Files\Sublime Text 3\subl.exe",
                        r"C:\Program Files\Sublime Text\subl.exe",
                        r"C:\Program Files\Sublime Text 3\sublime_text.exe",
                        r"C:\Program Files\Sublime Text\sublime_text.exe",
                    ]:
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

        # 2. Check for Sublime Text directly
        subl_candidates = [
            r"C:\Program Files\Sublime Text 3\subl.exe",
            r"C:\Program Files\Sublime Text\subl.exe",
            r"C:\Program Files\Sublime Text 3\sublime_text.exe",
            r"C:\Program Files\Sublime Text\sublime_text.exe",
            r"C:\Program Files (x86)\Sublime Text 3\subl.exe",
        ]
        for candidate in subl_candidates:
            if os.path.exists(candidate):
                try:
                    subprocess.Popen([candidate, target_file])
                    self.status_msg = "Opened history in Sublime Text"
                    return
                except Exception:
                    continue

        # 3. Fallback to Windows default registered editor for .txt
        try:
            os.startfile(target_file)
            self.status_msg = "Opened history in default editor"
            return
        except Exception:
            pass

        # 4. Fallback to Notepad
        try:
            subprocess.Popen(["notepad.exe", target_file])
            self.status_msg = "Opened history in Notepad"
        except Exception as e:
            self.status_msg = f"Error opening editor: {e}"

    def action_reload_history(self) -> None:
        self.load_history()

    def get_selected_command(self) -> Optional[str]:
        table = self.query_one("#history_table", DataTable)
        row = table.cursor_row
        if row is not None and 0 <= row < len(self.filtered_indices):
            real_idx = self.filtered_indices[row]
            return self.all_commands[real_idx]
        return None

if __name__ == "__main__":
    app = HistoryDashboard()
    app.run()