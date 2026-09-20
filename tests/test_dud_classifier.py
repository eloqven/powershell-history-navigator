import pytest
from history_tui import is_dud_command, get_history_file_path

def test_valid_commands():
    valid_samples = [
        "git status",
        "Get-ChildItem -Path C:\\Users -Recurse",
        "python -m pytest tests/",
        "docker compose up -d --build",
        "$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession",
        "$items | Where-Object { $_.Length -gt 100 } | Select-Object -First 10",
        "& 'C:\\Program Files\\Python\\python.exe' script.py",
        "npm run build -- --env=production",
        "$str = 'Hello world'",
        "$str = \"Double quotes with 'nested' quotes\"",
        "$map = @{ 'key' = 'value'; 'num' = 42 }",
        "[System.IO.File]::ReadAllText($path)",
        "./scripts/run.ps1",
    ]
    for cmd in valid_samples:
        assert not is_dud_command(cmd), f"Valid command incorrectly flagged as dud: {cmd}"

def test_dud_error_tracebacks():
    dud_samples = [
        "+ CategoryInfo          : ObjectNotFound: (foo:String) [], CommandNotFoundException",
        "+ FullyQualifiedErrorId : CommandNotFoundException",
        "At line:10 char:1",
        "At C:\\Users\\setup.ps1:15 char:4",
        "foo : The term 'foo' is not recognized as the name of a cmdlet, function, script file",
        "that the path is correct and try again.",
        "+ ~~~~~~~~~~~~~~~~~~~~~~",
        "^^^^^^^^^^^^^^^^^^^^^^^",
        "+ ^^^^^^",
    ]
    for cmd in dud_samples:
        assert is_dud_command(cmd), f"Error trace line should be detected as dud: {cmd}"

def test_dud_prompt_continuations_and_dangling_escapes():
    prompt_samples = [
        ">> asdfasdfasdfasdf",
        ">> sdasdfasdfasdf",
        ">> Get-Process",
        ">>> nested prompt copy paste",
        "PS C:\\Users\\admin> Get-ChildItem",
        "sdasdfadsfasdfasdf`",
        "git commit -m `",
    ]
    for cmd in prompt_samples:
        assert is_dud_command(cmd), f"Prompt continuation or dangling escape should be flagged as dud: {cmd}"

def test_dud_keyboard_mash_spam():
    mash_samples = [
        "asdfasdfasdfasdf",
        "sdasdfasdfasdf",
        "sdasdfadsfasdfasdf",
        "aaaaaa",
        "qwerqwerqwer",
        "zxcvzxcvzxcv",
    ]
    for cmd in mash_samples:
        assert is_dud_command(cmd), f"Keyboard mash / spam should be flagged as dud: {cmd}"

def test_dud_unbalanced_quotes():
    unbalanced_samples = [
        "git commit -m 'unclosed single quote",
        'git commit -m "unclosed double quote',
        'Write-Host "Unclosed double quote with $var',
        "python -c 'print(\"unclosed single quote)",
    ]
    for cmd in unbalanced_samples:
        assert is_dud_command(cmd), f"Unbalanced quote command should be flagged as dud: {cmd}"

def test_dud_unbalanced_brackets():
    unbalanced_samples = [
        "pip install imageio[ffmpeg])",
        "Get-Process | Where-Object { $_.CPU -gt 10",
        "function test {",
        "$arr = @(1, 2, 3",
        "(1 + 2 * (3 + 4)",
        "Write-Host 'hello' )",
    ]
    for cmd in unbalanced_samples:
        assert is_dud_command(cmd), f"Unbalanced bracket command should be flagged as dud: {cmd}"

def test_dud_leading_invalid_punctuation():
    invalid_leading = [
        ";s",
        "| Select-Object",
        ", 1, 2, 3",
        "} else {",
        ")",
        "]",
        "> output.txt",
    ]
    for cmd in invalid_leading:
        assert is_dud_command(cmd), f"Invalid leading punctuation should be flagged as dud: {cmd}"
