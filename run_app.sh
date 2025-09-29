#!/bin/zsh
# Set the ZBar library path
export DYLD_LIBRARY_PATH="/opt/homebrew/opt/zbar/lib:$DYLD_LIBRARY_PATH"

# Activate the virtual environment
source .venv/bin/activate

# Run the application
python main.py
