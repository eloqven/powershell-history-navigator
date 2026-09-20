# PowerShell script to run the TUI application

# Check if the required Python package 'textual' is installed
if (-not (pip show textual > $null 2>&1)) {
    Write-Host "Installing required package 'textual'..."
    pip install textual
}

# Run the TUI application
python "$PSScriptRoot/history_tui.py"