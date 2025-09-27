#!/bin/bash

# Start virtual display
export DISPLAY=:99
Xvfb :99 -screen 0 1280x800x24 > /dev/null 2>&1 &

# Wait for display to be ready
sleep 2

# Activate virtual environment
source venv/bin/activate

# Start Streamlit app
streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0