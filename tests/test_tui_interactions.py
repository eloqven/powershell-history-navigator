import pytest
from history_tui import HistoryDashboard, SearchInput
from textual.widgets import DataTable

@pytest.mark.anyio
async def test_colon_command_mode_selection_retention():
    """Verify that pressing ':' when search bar is unfocused does not select ':'
    and allow subsequent characters like 'red' to produce ':red' instead of 'red'.
    """
    app = HistoryDashboard()
    async with app.run_test() as pilot:
        table = app.query_one("#history_table", DataTable)
        inp = app.query_one("#search_input", SearchInput)
        
        # Ensure table is focused initially
        assert app.focused == table
        assert inp.value == ""
        
        # Press ':' to enter command mode
        await pilot.press("colon")
        assert app.focused == inp
        assert inp.value == ":"
        
        # Type 'r', 'e', 'd'
        await pilot.press("r")
        await pilot.press("e")
        await pilot.press("d")
        
        # The input must contain ':red'
        assert inp.value == ":red", f"Expected ':red' but got '{inp.value}'"

@pytest.mark.anyio
async def test_slash_search_focus_and_typing():
    """Verify that pressing '/' focuses the search bar and allows typing query."""
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
    """Verify that typing ':tokyo' switches theme."""
    app = HistoryDashboard()
    async with app.run_test() as pilot:
        inp = app.query_one("#search_input", SearchInput)
        
        await pilot.press("colon")
        await pilot.press("t", "o", "k", "y", "o")
        await pilot.press("enter")
        
        assert app.current_theme_idx == 2
        assert "theme-tokyonight" in app.screen.classes

@pytest.mark.anyio
async def test_help_modal_t_and_r_keys():
    """Verify that 't' toggles theme inside HelpModal and 'r' reloads & closes modal."""
    app = HistoryDashboard()
    async with app.run_test() as pilot:
        # Open help modal
        await pilot.press("question_mark")
        from history_tui import HelpModal
        assert isinstance(app.screen, HelpModal)
        
        # Press 't' in modal to cycle theme
        assert app.current_theme_idx == 0
        await pilot.press("t")
        assert app.current_theme_idx == 1
        assert "theme-dracula" in app.screen.classes
        
        # Press 'r' in modal: should dismiss modal and reload
        await pilot.press("r")
        await pilot.pause()
        assert not isinstance(app.screen, HelpModal)
