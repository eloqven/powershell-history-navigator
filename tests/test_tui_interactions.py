import pytest
from textual.widgets import Button, DataTable, Input
from history_tui import EditCommandModal, HelpModal, HistoryDashboard, SearchInput

@pytest.fixture(autouse=True)
def temp_history(tmp_path, monkeypatch):
    history_file = tmp_path / "test_history.txt"
    content = (
        "git status\n"
        "cd C:\\Projects\n"
        "git commit -m \"fix:red-alert\"\n"
        "+ CategoryInfo : NotSpecified: (:) [], RemoteException\n"
        "git log --format:%s\n"
        "Get-Process\n"
    )
    history_file.write_text(content, encoding="utf-8")
    monkeypatch.setattr(HistoryDashboard, "history_path", history_file)
    return history_file

@pytest.mark.anyio
async def test_enter_key_opens_run_modal():
    """Verify that pressing Enter on a command opens the Edit & Execute modal."""
    app = HistoryDashboard()
    async with app.run_test() as pilot:
        table = app.query_one("#history_table", DataTable)
        assert app.focused == table

        # Press Enter on selected row to open modal
        await pilot.press("enter")
        assert isinstance(app.screen, EditCommandModal)

        modal_inp = app.screen.query_one("#edit_input", Input)
        assert len(modal_inp.value) > 0

        # Press Escape to cancel modal
        await pilot.press("escape")
        assert not isinstance(app.screen, EditCommandModal)

@pytest.mark.anyio
async def test_modal_run_in_terminal(monkeypatch):
    """Verify that pressing Enter inside modal triggers launch_in_terminal and copy_to_clipboard."""
    launched = []
    copied = []
    monkeypatch.setattr("history_tui.launch_in_terminal", lambda cmd: launched.append(cmd) or True)
    monkeypatch.setattr("history_tui.copy_to_clipboard", lambda cmd: copied.append(cmd) or True)

    app = HistoryDashboard()
    async with app.run_test() as pilot:
        # Open modal with Enter on table row
        await pilot.press("enter")
        assert isinstance(app.screen, EditCommandModal)

        # Press Enter inside input to trigger 'Run in Terminal'
        await pilot.press("enter")
        await pilot.pause()

        assert not isinstance(app.screen, EditCommandModal)
        assert len(launched) == 1
        assert len(copied) == 1
        assert launched[0] == copied[0]

@pytest.mark.anyio
async def test_modal_save_to_disk():
    """Verify that clicking Save to Disk updates history on disk without launching terminal."""
    app = HistoryDashboard()
    async with app.run_test() as pilot:
        await pilot.press("enter")
        assert isinstance(app.screen, EditCommandModal)

        modal_inp = app.screen.query_one("#edit_input", Input)
        modal_inp.value = "git status --short"

        btn_save = app.screen.query_one("#btn_save", Button)
        btn_save.press()
        await pilot.pause()

        assert not isinstance(app.screen, EditCommandModal)
        assert "git status --short" in app.all_commands

@pytest.mark.anyio
async def test_colon_live_filtering_and_dud_command():
    """Verify that typing ':' filters commands containing ':' normally,
    and only when the full ':red' command is entered does it switch to dud-only filtering.
    """
    app = HistoryDashboard()
    async with app.run_test() as pilot:
        inp = app.query_one("#search_input", SearchInput)
        table = app.query_one("#history_table", DataTable)

        # Initially all 6 commands loaded
        assert len(app.filtered_indices) == 6

        # Typing ':' matches 4 commands containing ':' (cd C:\..., fix:red-alert, CategoryInfo, git log --format:%s)
        await pilot.press("colon")
        assert inp.value == ":"
        assert len(app.filtered_indices) == 4

        # Typing 'r' gives ':r' -> matches 'fix:red-alert'
        await pilot.press("r")
        assert inp.value == ":r"
        assert len(app.filtered_indices) == 1
        assert app.filtered_indices[0] == 2  # 'git commit -m "fix:red-alert"'

        # Typing 'e' gives ':re' -> matches 'fix:red-alert'
        await pilot.press("e")
        assert inp.value == ":re"
        assert len(app.filtered_indices) == 1

        # Typing 'd' gives ':red' -> completed special trigger! Switches to filtering ALL syntax duds
        await pilot.press("d")
        assert inp.value == ":red"
        assert len(app.filtered_indices) == 1
        assert app.filtered_indices[0] == 3  # '+ CategoryInfo : ...' (the syntax dud)
        assert app.dud_flags[app.filtered_indices[0]] is True

@pytest.mark.anyio
async def test_slash_search_focus_and_typing():
    app = HistoryDashboard()
    async with app.run_test() as pilot:
        table = app.query_one("#history_table", DataTable)
        inp = app.query_one("#search_input", SearchInput)

        assert app.focused == table
        await pilot.press("slash")
        assert app.focused == inp

        await pilot.press("g", "i", "t")
        assert inp.value == "git"
        assert len(app.filtered_indices) == 3  # 'git status', 'git commit...', 'git log...'

@pytest.mark.anyio
async def test_theme_toggle_command():
    app = HistoryDashboard()
    async with app.run_test() as pilot:
        await pilot.press("colon")
        await pilot.press("t", "o", "k", "y", "o")
        await pilot.press("enter")

        assert app.current_theme_idx == 2
        assert "theme-tokyonight" in app.screen.classes

@pytest.mark.anyio
async def test_help_modal_t_and_r_keys():
    app = HistoryDashboard()
    async with app.run_test() as pilot:
        await pilot.press("question_mark")
        assert isinstance(app.screen, HelpModal)

        assert app.current_theme_idx == 0
        await pilot.press("t")
        assert app.current_theme_idx == 1
        assert "theme-dracula" in app.screen.classes

        await pilot.press("r")
        await pilot.pause()
        assert not isinstance(app.screen, HelpModal)
