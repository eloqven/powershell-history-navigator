---
module: history_tui
date: 2026-09-20
problem_type: ui_bug
component: frontend
severity: medium
symptoms:
  - "Pressing ':' to trigger Command Mode when the history table is focused selects the newly inserted ':' character"
  - "Typing subsequent characters (such as 'red' for ':red') replaces the selection and erases the ':' prefix"
  - "Command Mode commands fail to execute because input receives only 'red' instead of ':red'"
root_cause: wrong_api
resolution_type: code_fix
tags:
  - textual
  - tui
  - input-widget
  - focus-handling
  - selection
  - command-mode
---

# Textual Input Focus Selection Overwrite in Command Mode

## Problem

When activating Command Mode by pressing `:` while the history DataTable is focused, the search input widget received focus and automatically highlighted/selected the `:` character. Typing subsequent keys immediately overwrote the `:`, preventing command execution.

## Symptoms

- Pressing `:` while navigating history rows focused the input bar and inserted `:`, but typing `red` resulted in `red` instead of `:red`.
- Command mode filter triggers like `:red`, `:duds`, `:sort`, `:theme`, and `:q` failed because the leading colon was replaced on the first subsequent keypress.

## What Didn't Work

- **Setting `inp.selection = Selection.cursor(...)` manually**: Setting `inp.selection` directly required importing internal selection classes and caused `NameError` if imports were pruned or changed across Textual versions.
- **Focusing before prepending `:`**: Calling `inp.focus()` before modifying `inp.value` still triggered Textual's default focus handler, which highlights all existing text when focus changes.

## Solution

1. Subclass `Input` as `SearchInput` and pass `select_on_focus=False` to `super().__init__()`.
2. In `action_focus_search()`, set `inp.cursor_position = len(inp.value)` after focusing. In Textual, setting `cursor_position` automatically syncs and clears selection to a single cursor point without needing internal `Selection` objects.
3. In `action_focus_colon_search()`, prepend `:` if missing and delegate directly to `self.action_focus_search()`.

### Code Changes

In `history_tui.py`:

```python
class SearchInput(Input):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, select_on_focus=False, **kwargs)

    BINDINGS = [
        Binding("up", "app.nav_up", "Up", show=False),
        Binding("down", "app.nav_down", "Down", show=False),
        Binding("escape", "app.clear_or_blur", "Cancel", show=False),
    ]
```

```python
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
```

## Why This Works

Textual's `Input` widget has `select_on_focus = True` by default, which causes any focus event to select the entire input string. Passing `select_on_focus=False` prevents automatic range selection on focus, ensuring typed keys append after existing characters. Setting `inp.cursor_position = len(inp.value)` ensures the cursor stays at the end of the text.

## Prevention

- **Disable `select_on_focus` for modal/command inputs**: When an `Input` widget serves as a command prompt or append-only search box, always pass `select_on_focus=False`.
- **Use `cursor_position` instead of raw `selection`**: Rely on `inp.cursor_position` to move the caret, which Textual internally maps to `Selection.cursor(position)`.
- **Add Pilot interaction tests for multi-character sequences**: Test sequential keypresses across focus shifts using Textual's `pilot.press("colon")` followed by `pilot.press("r", "e", "d")` to assert `inp.value == ":red"`.
