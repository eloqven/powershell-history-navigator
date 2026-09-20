import pytest
from textual.widgets import DataTable
from history_tui import HelpModal, HistoryDashboard, SearchInput

@pytest.fixture(autouse=True)
def temp_history(tmp_path, monkeypatch):
    history_file = tmp_path / "test_history.txt"
    history_file.write_text("git status\nGet-Process\nls -la\n", encoding="utf-8")
    monkeypatch.setattr(HistoryDashboard, "history_path", history_file)
    return history_file

@pytest.mark.anyio
async def test_colon_command_mode_selection_retention():
    app = HistoryDashboard()
    async with app.run_test() as pilot:
        table = app.query_one("#history_table", DataTable)
        inp = app.query_one("#search_input", SearchInput)

        assert app.focused == table
        assert inp.value == ""

        await pilot.press("colon")
        assert app.focused == inp
        assert inp.value == ":"

        await pilot.press("r", "e", "d")
        assert inp.value == ":red"

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
