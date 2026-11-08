from pathlib import Path
import pandas as pd

def get_latest_output_dir() -> Path:
    """Auto-detect the most recent experiment output directory."""
    base = Path(__file__).parents[1] / "experiment_output"
    dirs = [d for d in base.iterdir() if d.is_dir()]
    if not dirs:
        raise FileNotFoundError(f"No experiment output directories found in {base}")
    return max(dirs, key=lambda d: d.stat().st_mtime)

DEFAULT_OUTPUT_DIR = get_latest_output_dir()

def load_summary(output_dir: Path = None) -> pd.DataFrame:
    return pd.read_csv((output_dir or DEFAULT_OUTPUT_DIR) / "simulation_summary.csv")

def load_tracks(output_dir: Path = None) -> pd.DataFrame:
    return pd.read_csv((output_dir or DEFAULT_OUTPUT_DIR) / "track_performance.csv")

def load_incidents(output_dir: Path = None) -> pd.DataFrame:
    return pd.read_csv((output_dir or DEFAULT_OUTPUT_DIR) / "incident_log.csv")

def load_bags(output_dir: Path = None) -> pd.DataFrame:
    return pd.read_csv((output_dir or DEFAULT_OUTPUT_DIR) / "bag_details.csv")

def load_all_datasets(output_dir: Path = None) -> dict[str, pd.DataFrame]:
    return {
        "summary": load_summary(output_dir),
        "tracks": load_tracks(output_dir),
        "incidents": load_incidents(output_dir),
        "bags": load_bags(output_dir),
    }