import sys
from pathlib import Path

# Add repo root to path so 'analysis' package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from analysis.load_data import load_all_datasets


def post_process(output_dir: Path, experiment_config=None):
    """Clean and transform raw experiment CSVs for analysis/BI.

    Args:
        output_dir: Path to experiment output directory (containing raw CSVs)
        experiment_config: Optional ExperimentConfig for metadata
    """
    # Load all datasets from the specified output directory
    data = load_all_datasets(output_dir)
    summary = data["summary"]
    tracks = data["tracks"]
    incidents = data["incidents"]
    bags = data["bags"]

    print(f"Post-processing: {output_dir}")

    # General cleaning of the data from simulation results
    summary = summary.drop(columns=['total_ticks', 'timestamp', 'notes'], errors='ignore')
    summary.drop_duplicates(inplace=True)
    tracks.drop_duplicates(inplace=True)
    incidents.drop_duplicates(inplace=True)
    bags.drop_duplicates(inplace=True)

    # Add derived metrics
    if 'misrouted_bags' in summary.columns and 'total_bags' in summary.columns:
        summary['misrouted_rate'] = summary['misrouted_bags'] / summary['total_bags']
    if 'delivery_time' in bags.columns:
        bags['delivery_time'] = pd.to_numeric(bags['delivery_time'], errors='coerce')
        bags['is_misrouted'] = bags['misrouted'].astype(bool)

    # Export cleaned CSVs to same directory (overwrites raw)
    summary.to_csv(output_dir / "simulation_summary.csv", index=False)
    tracks.to_csv(output_dir / "track_performance.csv", index=False)
    incidents.to_csv(output_dir / "incident_log.csv", index=False)
    bags.to_csv(output_dir / "bag_details.csv", index=False)

    print(f"  Cleaned 4 CSVs written to {output_dir}")

    return {
        "summary": summary,
        "tracks": tracks,
        "incidents": incidents,
        "bags": bags
    }


if __name__ == "__main__":
    # CLI usage: python -m analysis.analysiswork --output_dir experiment_output/run_id
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", type=Path, required=True, help="Experiment output directory")
    args = parser.parse_args()
    post_process(args.output_dir)