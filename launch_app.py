"""
Open the PMI Streamlit app.  In VS Code: open this file and press Run (triangle).
Same as typing:  python -m streamlit run app.py
Stop it with the trash-can / Ctrl+C in the terminal.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
subprocess.run([sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py")], cwd=ROOT)
