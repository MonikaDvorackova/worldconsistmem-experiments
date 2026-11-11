"""Streamlit Community Cloud entrypoint for WorldConsistMem annotation."""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).parent / "human_evaluation" / "app.py"), run_name="__main__")
