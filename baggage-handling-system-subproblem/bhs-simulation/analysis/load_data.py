from pathlib import Path
import pandas as pd
from typing import Optional

def get_latest_output_dir() -> Optional[Path]:
    """Auto-detect the most recent experiment output directory. Returns None if not found."""
    base = Path(__file__).parents[1] / "experiment_output"
    if not base.exists():
        return None
    dirs = [d for d in base.iterdir() if d.is_dir()]
    if not dirs:
        return None
    return max(dirs, key=lambda d: d.stat().st_mtime)

# Lazy evaluation - only compute when needed
_DEFAULT_OUTPUT_DIR = None

def _get_default_output_dir() -> Optional[Path]:
    global _DEFAULT_OUTPUT_DIR
    if _DEFAULT_OUTPUT_DIR is None:
        _DEFAULT_OUTPUT_DIR = get_latest_output_dir()
    return _DEFAULT_OUTPUT_DIR

def load_summary(output_dir: Path = None) -> pd.DataFrame:
    dir = output_dir or _get_default_output_dir()
    if dir is None:
        raise FileNotFoundError("No experiment output directory found. Run an experiment first.")
    return pd.read_csv(dir / "simulation_summary.csv")

def load_tracks(output_dir: Path = None) -> pd.DataFrame:
    dir = output_dir or _get_default_output_dir()
    if dir is None:
        raise FileNotFoundError("No experiment output directory found. Run an experiment first.")
    return pd.read_csv(dir / "track_performance.csv")

def load_incidents(output_dir: Path = None) -> pd.DataFrame:
    dir = output_dir or _get_default_output_dir()
    if dir is None:
        raise FileNotFoundError("No experiment output directory found. Run an experiment first.")
    return pd.read_csv(dir / "incident_log.csv")

def load_bags(output_dir: Path = None) -> pd.DataFrame:
    dir = output_dir or _get_default_output_dir()
    if dir is None:
        raise FileNotFoundError("No experiment output directory found. Run an experiment first.")
    return pd.read_csv(dir / "bag_details.csv")

def load_all_datasets(output_dir: Path = None) -> dict[str, pd.DataFrame]:
    dir = output_dir or _get_default_output_dir()
    if dir is None:
        raise FileNotFoundError("No experiment output directory found. Run an experiment first.")
    return {
        "summary": load_summary(dir),
        "tracks": load_tracks(dir),
        "incidents": load_incidents(dir),
        "bags": load_bags(dir),
    }