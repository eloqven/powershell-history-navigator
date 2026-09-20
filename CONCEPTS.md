# Concepts

> Shared domain vocabulary for this project — entities, named processes, and status concepts with project-specific meaning. Seeded with core domain vocabulary, then accretes as ce-compound and ce-compound-refresh process learnings; direct edits are fine. Glossary only, not a spec or catch-all.

## Navigation & Modes

### Command Mode
An interactive input mode activated by a leading colon (`:`) in the search bar that dispatches internal management commands (such as theme switching, in-place edits, sort order inversion, and bulk deletion) instead of performing substring searches against history records.

### Live Search Filter
A real-time search state that dynamically filters and highlights command history entries matching query substrings across command index, length, and text content.

## Command Health & Quality

### Syntax Dud
A history entry classified as non-executable terminal debris (including syntax errors, unmatched quotes, unclosed brackets, dangling delimiters, and pasted error tracebacks) isolated with visual indicators for targeted filtering and cleanup.
*Aliases:* Dud, Error Command, Bad Syntax

## Maintenance Operations

### In-Place Edit
A focused modal editing workflow that loads a selected historical command into an isolated editor modal and updates the entry directly on disk in the PowerShell history file without disturbing other records.

### Double-Confirmation Purge
A two-stage guarded deletion workflow requiring explicit sequential confirmations before permanently removing filtered command sets from the history file on disk.
