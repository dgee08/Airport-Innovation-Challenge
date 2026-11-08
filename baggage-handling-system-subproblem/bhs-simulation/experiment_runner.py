"""
Simulation Experiment Runner for Baggage Handling System
Supports configurable scenarios, repeatable runs, and structured CSV exports for Power BI.
"""
import json
import csv
import sys
import os
import uuid
import random
import importlib
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent

# Import existing modules
sys.path.insert(0, str(BASE_DIR))
from evaluator import BaggageEvaluator
import solution
import oursolution

# Import post-processing (optional, for cleaned CSVs)
try:
    from analysis.analysiswork import post_process
    POST_PROCESS_AVAILABLE = True
except ImportError:
    POST_PROCESS_AVAILABLE = False
    post_process = None


# =============================================================================
# EXPERIMENT CONFIGURATION
# =============================================================================

@dataclass
class ExperimentConfig:
    """Configuration for a single experiment run."""
    experiment_id: str
    scenario_name: str
    seed: int
    bag_volume_multiplier: float = 1.0
    additional_jams: List[Dict] = None
    foreign_object_scenarios: List[Dict] = None
    # Diversion configuration
    diversion_threshold: float = 0.7
    diversion_capacity: int = 50
    diversion_node: str = "DIVERSION_INSPECTION"
    notes: str = ""

    def __post_init__(self):
        if self.additional_jams is None:
            self.additional_jams = []
        if self.foreign_object_scenarios is None:
            self.foreign_object_scenarios = []


@dataclass
class SimulationSummary:
    """Summary metrics for a single simulation run."""
    experiment_id: str
    scenario_name: str
    seed: int
    bag_volume_multiplier: float
    total_bags: int
    delivered_bags: int
    stranded_bags: int
    misrouted_bags: int
    mean_delivery_latency: float
    total_jams_triggered: int
    misrouted_rate: float = 0.0
    notes: str = ""


# =============================================================================
# SCENARIO DEFINITIONS
# =============================================================================

SCENARIOS = {
    "baseline": {
        "description": "Standard procedural scenario with 5 phases and 14 strategic jams",
        "bag_volume_multiplier": 1.0,
        "additional_jams": [],
        "foreign_object_scenarios": [],
        "diversion_threshold": 0.7,
        "diversion_capacity": 50,
        "diversion_node": "DIVERSION_INSPECTION",
    },
    "high_demand": {
        "description": "Increased bag volume (1.5x) with same jam schedule",
        "bag_volume_multiplier": 1.5,
        "additional_jams": [],
        "foreign_object_scenarios": [],
        "diversion_threshold": 0.7,
        "diversion_capacity": 50,
        "diversion_node": "DIVERSION_INSPECTION",
    },
    "conveyor_failures": {
        "description": "Baseline bags with additional critical conveyor failures",
        "bag_volume_multiplier": 1.0,
        "additional_jams": [
            {"edge_id": "e_S2_S3", "start_tick": 500, "duration": 200, "note": "Extended spine trunk failure"},
            {"edge_id": "e_S3_S4", "start_tick": 1200, "duration": 150, "note": "Central spine failure during sustained load"},
            {"edge_id": "e_JA1_JB1", "start_tick": 2000, "duration": 300, "note": "Cross-terminal bridge failure"},
        ],
        "foreign_object_scenarios": [],
        "diversion_threshold": 0.7,
        "diversion_capacity": 50,
        "diversion_node": "DIVERSION_INSPECTION",
    },
    "congestion": {
        "description": "High demand with additional bottleneck jams",
        "bag_volume_multiplier": 1.3,
        "additional_jams": [
            {"edge_id": "e_JA2_S2", "start_tick": 800, "duration": 120, "note": "Terminal A spine feeder bottleneck"},
            {"edge_id": "e_JB2_S4", "start_tick": 800, "duration": 120, "note": "Terminal B spine feeder bottleneck"},
            {"edge_id": "e_S1_S6", "start_tick": 1600, "duration": 100, "note": "Detour belt congestion"},
            {"edge_id": "e_S6_S5", "start_tick": 1620, "duration": 100, "note": "Detour exit congestion"},
        ],
        "foreign_object_scenarios": [],
        "diversion_threshold": 0.7,
        "diversion_capacity": 50,
        "diversion_node": "DIVERSION_INSPECTION",
    },
    "foreign_objects": {
        "description": "Baseline with simulated foreign object incidents on key tracks",
        "bag_volume_multiplier": 1.0,
        "additional_jams": [],
        "foreign_object_scenarios": [
            {"track_id": "e_JA3_S3", "start_tick": 1850, "duration": 45, "severity": "WARNING", "object_type": "DEBRIS", "description": "Debris on Terminal A spine feed"},
            {"track_id": "e_S2_S3", "start_tick": 2200, "duration": 120, "severity": "CRITICAL", "object_type": "SPILLAGE", "description": "Fluid spillage on main spine trunk"},
            {"track_id": "e_JB2_S4", "start_tick": 2600, "duration": 80, "severity": "WARNING", "object_type": "OBSTRUCTION", "description": "Obstruction on Terminal B junction exit"},
            {"track_id": "e_S4_S5", "start_tick": 3180, "duration": 180, "severity": "EMERGENCY", "object_type": "OBSTRUCTION", "description": "Large obstruction on spine trunk"},
        ],
        "diversion_threshold": 0.7,
        "diversion_capacity": 50,
        "diversion_node": "DIVERSION_INSPECTION",
    },
    "suspicious_bags": {
        "description": "Baseline with increased cross-terminal routing to trigger suspicious detection",
        "bag_volume_multiplier": 1.2,
        "additional_jams": [
            {"edge_id": "e_JA1_JB1", "start_tick": 1000, "duration": 500, "note": "Cross-terminal bridge partially jammed"},
        ],
        "foreign_object_scenarios": [],
        "diversion_threshold": 0.7,
        "diversion_capacity": 50,
        "diversion_node": "DIVERSION_INSPECTION",
    },
    "combined_stress": {
        "description": "Maximum stress: high demand, multiple failures, foreign objects",
        "bag_volume_multiplier": 1.4,
        "additional_jams": [
            {"edge_id": "e_S2_S3", "start_tick": 500, "duration": 200, "note": "Spine trunk failure"},
            {"edge_id": "e_JA2_S2", "start_tick": 800, "duration": 120, "note": "Terminal A feeder bottleneck"},
            {"edge_id": "e_JB2_S4", "start_tick": 800, "duration": 120, "note": "Terminal B feeder bottleneck"},
            {"edge_id": "e_JA1_JB1", "start_tick": 2000, "duration": 300, "note": "Cross-terminal bridge failure"},
            {"edge_id": "e_S4_S5", "start_tick": 3150, "duration": 150, "note": "Wind-down blockade"},
        ],
        "foreign_object_scenarios": [
            {"track_id": "e_JA3_S3", "start_tick": 1850, "duration": 45, "severity": "WARNING", "object_type": "DEBRIS", "description": "Debris on Terminal A spine feed"},
            {"track_id": "e_S2_S3", "start_tick": 2200, "duration": 120, "severity": "CRITICAL", "object_type": "SPILLAGE", "description": "Fluid spillage on main spine trunk"},
            {"track_id": "e_S4_S5", "start_tick": 3180, "duration": 180, "severity": "EMERGENCY", "object_type": "OBSTRUCTION", "description": "Large obstruction on spine trunk"},
        ],
        "diversion_threshold": 0.7,
        "diversion_capacity": 50,
        "diversion_node": "DIVERSION_INSPECTION",
    },
}


# =============================================================================
# SCENARIO GENERATION
# =============================================================================

def generate_scenario(config: ExperimentConfig, base_scenario_path: Path) -> Dict:
    """Generate a modified scenario based on experiment configuration."""
    with open(base_scenario_path, 'r') as f:
        scenario = json.load(f)

    # Set random seed for reproducible bag generation
    random.seed(config.seed)

    # Modify bag volumes by adjusting density probabilities
    multiplier = config.bag_volume_multiplier
    if multiplier != 1.0:
        # We'll regenerate bags with modified probabilities
        # For now, scale by adding more bags proportionally
        pass  # Bag generation happens in generate_scenario.py with fixed seed

    # Add additional jams
    for jam in config.additional_jams:
        scenario["jams"].append({
            "jam_id": f"J{len(scenario['jams'])+1:03d}",
            "edge_id": jam["edge_id"],
            "start_tick": jam["start_tick"],
            "duration": jam["duration"],
            "note": jam["note"]
        })

    # Sort jams by start tick
    scenario["jams"].sort(key=lambda j: j["start_tick"])

    # Add diversion configuration
    scenario["diversion"] = {
        "threshold": config.diversion_threshold,
        "capacity": config.diversion_capacity,
        "node": config.diversion_node
    }

    return scenario


def regenerate_bags_with_multiplier(scenario: Dict, multiplier: float, seed: int) -> List[Dict]:
    """Regenerate bags with volume multiplier applied to spawn probabilities."""
    random.seed(seed)

    intake_nodes = ["IA1", "IA2", "IB1", "IB2"]
    a_gates = ["GA1", "GA2", "GA3", "GA4"]
    b_gates = ["GB1", "GB2", "GB3", "GB4"]
    all_gates = a_gates + b_gates

    bags = []
    bag_counter = 1

    def spawn_wave(start_tick, end_tick, base_density, strict_deadlines=False):
        nonlocal bag_counter
        density = min(1.0, base_density * multiplier)
        for t in range(start_tick, end_tick + 1):
            if random.random() < density:
                intake = random.choice(intake_nodes)
                if "A" in intake:
                    dest = random.choice(a_gates if random.random() < 0.8 else b_gates)
                else:
                    dest = random.choice(b_gates if random.random() < 0.8 else a_gates)

                bag_obj = {
                    "bag_id": f"B{bag_counter:04d}",
                    "intake_node": intake,
                    "destination_gate": dest,
                    "release_tick": t
                }

                if strict_deadlines or random.random() < 0.4:
                    window_size = random.randint(25, 35) if strict_deadlines else random.randint(45, 65)
                    bag_obj["deadline_tick"] = t + window_size

                bags.append(bag_obj)
                bag_counter += 1

    # Same phase structure as generate_scenario.py
    spawn_wave(1, 300, 0.05)
    spawn_wave(301, 900, 0.15)
    spawn_wave(901, 2100, 0.22)
    spawn_wave(2101, 3000, 0.38, strict_deadlines=True)
    spawn_wave(3001, 3300, 0.08)

    return bags


# =============================================================================
# EXTENDED EVALUATOR WITH DATA COLLECTION
# =============================================================================

class ExperimentEvaluator(BaggageEvaluator):
    """Extended evaluator that collects detailed data for export."""

    def __init__(self, layout_path, scenario_path, experiment_config: ExperimentConfig):
        super().__init__(layout_path, scenario_path)
        self.experiment_config = experiment_config
        self.incident_log = []  # Track jams and foreign objects
        self.bag_details = []   # Track per-bag details
        self._track_incidents_from_scenario()

    def _track_incidents_from_scenario(self):
        """Pre-populate incident log from scenario jams."""
        for jam in self.scenario.get("jams", []):
            self.incident_log.append({
                "tick": jam["start_tick"],
                "incident_type": "JAM",
                "severity": "CRITICAL" if "SCHEDULED" in jam.get("note", "") or "OVERLOAD" in jam.get("note", "") else "WARNING",
                "location": jam["edge_id"],
                "duration": jam["duration"],
                "resolution_status": "SCHEDULED",
                "description": jam.get("note", "")
            })
            # Add resolution event
            self.incident_log.append({
                "tick": jam["start_tick"] + jam["duration"],
                "incident_type": "JAM_CLEARED",
                "severity": "INFO",
                "location": jam["edge_id"],
                "duration": jam["duration"],
                "resolution_status": "RESOLVED",
                "description": f"Jam cleared: {jam.get('note', '')}"
            })

        # Add foreign object incidents from config
        for fo in self.experiment_config.foreign_object_scenarios:
            self.incident_log.append({
                "tick": fo["start_tick"],
                "incident_type": "FOREIGN_OBJECT",
                "severity": fo["severity"],
                "location": fo["track_id"],
                "duration": fo["duration"],
                "resolution_status": "DETECTED",
                "description": f"{fo['object_type']}: {fo['description']}"
            })
            self.incident_log.append({
                "tick": fo["start_tick"] + fo["duration"],
                "incident_type": "FOREIGN_OBJECT_CLEARED",
                "severity": "INFO",
                "location": fo["track_id"],
                "duration": fo["duration"],
                "resolution_status": "CLEARED",
                "description": f"Foreign object cleared: {fo['object_type']}"
            })

    def _apply_jam(self, target_id, duration, reason):
        """Override to log jam events."""
        super()._apply_jam(target_id, duration, reason)
        # Log dynamic jams (wear overload)
        if reason == "MECHANICAL_OVERLOAD":
            self.incident_log.append({
                "tick": self.current_tick,
                "incident_type": "JAM",
                "severity": "CRITICAL",
                "location": target_id,
                "duration": duration,
                "resolution_status": "TRIGGERED",
                "description": f"Mechanical overload on {target_id}"
            })

    def _log_diversion(self, bag_id, from_node, risk_score, original_destination):
        """Log diversion event."""
        self.incident_log.append({
            "tick": self.current_tick,
            "incident_type": "DIVERSION",
            "severity": "WARNING",
            "location": from_node,
            "duration": 0,
            "resolution_status": "DIVERTED",
            "description": f"Bag {bag_id} diverted from {from_node} to inspection (risk: {risk_score:.2f})"
        })

    def _log_dhs_telemetry(self):
        """Override to also track per-tick edge states for track performance."""
        super()._log_dhs_telemetry()

    def run(self, student_module):
        """Run simulation and collect bag details."""
        print(f"Initializing Experiment '{self.experiment_config.experiment_id}' ({self.total_ticks} Ticks)...")
        for tick in range(1, self.total_ticks + 1):
            self.current_tick = tick
            self._process_jams()
            self._spawn_baggage()
            self._advance_physics()
            self._execute_routing_decisions(student_module)
            self._log_dhs_telemetry()

        # Collect bag details after simulation
        self._collect_bag_details()

        self.export_logs()
        self.export_bag_logs()
        self._calculate_final_scores()

    def _collect_bag_details(self):
        """Collect detailed bag-level data."""
        for bag_id, bag in self.completed_bags.items():
            transit_time = bag["arrival_tick"] - bag["release_tick"]
            is_misrouted = False
            if bag["deadline_tick"] and bag["arrival_tick"] > bag["deadline_tick"]:
                is_misrouted = True
            is_diverted = bag.get("diverted", False)

            # Build route string from history
            route = " -> ".join([f"{node}(T{tick})" for node, tick in bag["history"]])

            self.bag_details.append({
                "experiment_id": self.experiment_config.experiment_id,
                "bag_id": bag_id,
                "origin": bag["history"][0][0] if bag["history"] else "UNKNOWN",
                "destination": bag["destination_gate"],
                "route": route,
                "release_tick": bag["release_tick"],
                "arrival_tick": bag["arrival_tick"],
                "delivery_time": transit_time,
                "deadline_tick": bag.get("deadline_tick"),
                "misrouted": is_misrouted,
                "diverted": is_diverted,
                "hops": len(bag["history"]) - 1
            })

        # Stranded bags
        for bag_id, bag in self.active_bags.items():
            self.bag_details.append({
                "experiment_id": self.experiment_config.experiment_id,
                "bag_id": bag_id,
                "origin": bag["history"][0][0] if bag["history"] else "UNKNOWN",
                "destination": bag["destination_gate"],
                "route": " -> ".join([f"{node}(T{tick})" for node, tick in bag["history"]]),
                "release_tick": bag["release_tick"],
                "arrival_tick": None,
                "delivery_time": None,
                "deadline_tick": bag.get("deadline_tick"),
                "misrouted": True,
                "diverted": False,
                "hops": len(bag["history"]) - 1
            })

    def get_summary(self) -> SimulationSummary:
        """Get simulation summary metrics."""
        total_bags = len(self.scenario["bags"])
        delivered_count = len(self.completed_bags)
        stranded_count = len(self.active_bags)

        misrouted_count = 0
        total_transit_time = 0

        for bag_id, bag in self.completed_bags.items():
            transit_time = bag["arrival_tick"] - bag["release_tick"]
            total_transit_time += transit_time
            if bag["deadline_tick"] and bag["arrival_tick"] > bag["deadline_tick"]:
                misrouted_count += 1

        misrouted_count += stranded_count
        mean_transit_time = (total_transit_time / delivered_count) if delivered_count > 0 else 0

        # Count total jams triggered (scheduled + wear overload)
        jam_count = sum(1 for inc in self.incident_log if inc["incident_type"] == "JAM")

        misrouted_rate = (misrouted_count / total_bags) if total_bags > 0 else 0.0

        return SimulationSummary(
            experiment_id=self.experiment_config.experiment_id,
            scenario_name=self.experiment_config.scenario_name,
            seed=self.experiment_config.seed,
            bag_volume_multiplier=self.experiment_config.bag_volume_multiplier,
            total_bags=total_bags,
            delivered_bags=delivered_count,
            stranded_bags=stranded_count,
            misrouted_bags=misrouted_count,
            mean_delivery_latency=round(mean_transit_time, 2),
            total_jams_triggered=jam_count,
            misrouted_rate=round(misrouted_rate, 6),
            notes=self.experiment_config.notes
        )


# =============================================================================
# CSV EXPORT
# =============================================================================

class ExperimentExporter:
    """Handles CSV export for experiment data."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_summary(self, summary: SimulationSummary):
        """Export simulation summary."""
        path = self.output_dir / "simulation_summary.csv"
        write_header = not path.exists()

        with open(path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=asdict(summary).keys())
            if write_header:
                writer.writeheader()
            writer.writerow(asdict(summary))

    def export_track_performance(self, evaluator: ExperimentEvaluator):
        """Export per-tick track performance data."""
        path = self.output_dir / "track_performance.csv"
        write_header = not path.exists()

        # Add experiment_id to each row
        rows = []
        for row in evaluator.dhs_log_data:
            rows.append({
                "experiment_id": evaluator.experiment_config.experiment_id,
                "scenario_name": evaluator.experiment_config.scenario_name,
                "seed": evaluator.experiment_config.seed,
                **row
            })

        if rows:
            with open(path, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                if write_header:
                    writer.writeheader()
                writer.writerows(rows)

    def export_incident_log(self, evaluator: ExperimentEvaluator):
        """Export incident log."""
        path = self.output_dir / "incident_log.csv"
        write_header = not path.exists()

        rows = []
        for inc in evaluator.incident_log:
            rows.append({
                "experiment_id": evaluator.experiment_config.experiment_id,
                "scenario_name": evaluator.experiment_config.scenario_name,
                "seed": evaluator.experiment_config.seed,
                **inc
            })

        if rows:
            with open(path, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                if write_header:
                    writer.writeheader()
                writer.writerows(rows)

    def export_bag_details(self, evaluator: ExperimentEvaluator):
        """Export bag-level data."""
        path = self.output_dir / "bag_details.csv"
        write_header = not path.exists()

        rows = []
        for bag in evaluator.bag_details:
            rows.append({
                "experiment_id": evaluator.experiment_config.experiment_id,
                "scenario_name": evaluator.experiment_config.scenario_name,
                "seed": evaluator.experiment_config.seed,
                **bag
            })

        if rows:
            with open(path, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                if write_header:
                    writer.writeheader()
                writer.writerows(rows)

    def export_all(self, evaluator: ExperimentEvaluator):
        """Export all datasets."""
        summary = evaluator.get_summary()
        self.export_summary(summary)
        self.export_track_performance(evaluator)
        self.export_incident_log(evaluator)
        self.export_bag_details(evaluator)
        print(f"  Exported 4 CSV files to {self.output_dir}")

    def export_summary_with_module(self, summary: SimulationSummary, module_name: str):
        """Export simulation summary with module name."""
        path = self.output_dir / f"simulation_summary_{module_name}.csv"
        write_header = not path.exists()

        # Add module to summary
        summary_dict = asdict(summary)
        summary_dict["routing_module"] = module_name

        with open(path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=summary_dict.keys())
            if write_header:
                writer.writeheader()
            writer.writerow(summary_dict)

    def export_track_performance_with_module(self, evaluator: ExperimentEvaluator, module_name: str):
        """Export per-tick track performance data with module name."""
        path = self.output_dir / f"track_performance_{module_name}.csv"
        write_header = not path.exists()

        rows = []
        for row in evaluator.dhs_log_data:
            rows.append({
                "experiment_id": evaluator.experiment_config.experiment_id,
                "scenario_name": evaluator.experiment_config.scenario_name,
                "seed": evaluator.experiment_config.seed,
                "routing_module": module_name,
                **row
            })

        if rows:
            with open(path, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                if write_header:
                    writer.writeheader()
                writer.writerows(rows)

    def export_incident_log_with_module(self, evaluator: ExperimentEvaluator, module_name: str):
        """Export incident log with module name."""
        path = self.output_dir / f"incident_log_{module_name}.csv"
        write_header = not path.exists()

        rows = []
        for inc in evaluator.incident_log:
            rows.append({
                "experiment_id": evaluator.experiment_config.experiment_id,
                "scenario_name": evaluator.experiment_config.scenario_name,
                "seed": evaluator.experiment_config.seed,
                "routing_module": module_name,
                **inc
            })

        if rows:
            with open(path, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                if write_header:
                    writer.writeheader()
                writer.writerows(rows)

    def export_bag_details_with_module(self, evaluator: ExperimentEvaluator, module_name: str):
        """Export bag-level data with module name."""
        path = self.output_dir / f"bag_details_{module_name}.csv"
        write_header = not path.exists()

        rows = []
        for bag in evaluator.bag_details:
            rows.append({
                "experiment_id": evaluator.experiment_config.experiment_id,
                "scenario_name": evaluator.experiment_config.scenario_name,
                "seed": evaluator.experiment_config.seed,
                "routing_module": module_name,
                **bag
            })

        if rows:
            with open(path, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                if write_header:
                    writer.writeheader()
                writer.writerows(rows)


# =============================================================================
# EXPERIMENT RUNNER
# =============================================================================

def run_experiment(config: ExperimentConfig, layout_path: Path, base_scenario_path: Path, output_dir: Path, routing_module=None) -> ExperimentEvaluator:
    """Run a single experiment with given configuration."""
    if routing_module is None:
        routing_module = solution

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate modified scenario
    scenario = generate_scenario(config, base_scenario_path)

    # Regenerate bags with volume multiplier
    if config.bag_volume_multiplier != 1.0:
        scenario["bags"] = regenerate_bags_with_multiplier(scenario, config.bag_volume_multiplier, config.seed)

    # Reset global state for optimized module before each run
    if hasattr(routing_module, 'reset'):
        routing_module.reset()

    # Write temporary scenario file
    temp_scenario_path = output_dir / f"temp_scenario_{config.experiment_id}.json"
    with open(temp_scenario_path, 'w') as f:
        json.dump(scenario, f, indent=2)

    # Run simulation
    evaluator = ExperimentEvaluator(layout_path, temp_scenario_path, config)
    evaluator.run(routing_module)

    # Export data
    exporter = ExperimentExporter(output_dir)
    exporter.export_all(evaluator)

    # Post-process: clean CSVs for analysis/BI
    if POST_PROCESS_AVAILABLE and post_process:
        try:
            post_process(output_dir, config)
        except Exception as e:
            print(f"  Post-processing warning: {e}")

    # Clean up temp file
    temp_scenario_path.unlink()

    return evaluator


def run_comparison_experiment(config: ExperimentConfig, layout_path: Path, base_scenario_path: Path, output_dir: Path) -> Dict:
    """Run both baseline and optimized solutions on the same scenario for comparison."""
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate modified scenario once (shared)
    scenario = generate_scenario(config, base_scenario_path)

    # Regenerate bags with volume multiplier
    if config.bag_volume_multiplier != 1.0:
        scenario["bags"] = regenerate_bags_with_multiplier(scenario, config.bag_volume_multiplier, config.seed)

    results = {}

    for module_name, module in [("baseline", solution), ("optimized", oursolution)]:
        exp_id = f"{config.experiment_id}_{module_name}"

        # Reset global state for optimized module before each run
        if hasattr(module, 'reset'):
            module.reset()

        # Write temporary scenario file
        temp_scenario_path = output_dir / f"temp_scenario_{exp_id}.json"
        with open(temp_scenario_path, 'w') as f:
            json.dump(scenario, f, indent=2)

        # Run simulation
        evaluator = ExperimentEvaluator(layout_path, temp_scenario_path, config)
        evaluator.run(module)

        # Export data with module suffix
        exporter = ExperimentExporter(output_dir)
        # Modify export to include module name
        summary = evaluator.get_summary()

        # Save with module-specific prefix
        exporter.export_summary_with_module(summary, module_name)
        exporter.export_track_performance_with_module(evaluator, module_name)
        exporter.export_incident_log_with_module(evaluator, module_name)
        exporter.export_bag_details_with_module(evaluator, module_name)

        # Clean up temp file
        temp_scenario_path.unlink()

        results[module_name] = {
            "evaluator": evaluator,
            "summary": summary
        }

        print(f"  {module_name}: {summary.delivered_bags}/{summary.total_bags} delivered, "
              f"{summary.misrouted_bags} misrouted, {summary.mean_delivery_latency:.1f} avg latency")

    return results


def run_experiment_suite(
    scenario_names: List[str],
    seeds: List[int] = None,
    repeats: int = 1,
    output_dir: Path = None,
    bag_multipliers: Dict[str, float] = None
):
    """Run a suite of experiments."""
    if output_dir is None:
        output_dir = BASE_DIR / "experiment_output" / datetime.now().strftime("%Y%m%d_%H%M%S")

    if seeds is None:
        seeds = [42, 123, 456, 789, 999]

    if bag_multipliers is None:
        bag_multipliers = {}

    layout_path = BASE_DIR / "data" / "network_layout.json"
    base_scenario_path = BASE_DIR / "data" / "simulation_scenario.json"

    print(f"=" * 60)
    print(f"EXPERIMENT SUITE STARTED")
    print(f"Output directory: {output_dir}")
    print(f"Scenarios: {scenario_names}")
    print(f"Seeds: {seeds}")
    print(f"Repeats per seed: {repeats}")
    print(f"=" * 60)

    results = []

    for scenario_name in scenario_names:
        if scenario_name not in SCENARIOS:
            print(f"WARNING: Unknown scenario '{scenario_name}', skipping")
            continue

        scenario_def = SCENARIOS[scenario_name]
        multiplier = bag_multipliers.get(scenario_name, scenario_def["bag_volume_multiplier"])

        for seed in seeds:
            for repeat in range(repeats):
                exp_id = f"{scenario_name}_seed{seed}_rep{repeat+1}_{uuid.uuid4().hex[:8]}"

                config = ExperimentConfig(
                    experiment_id=exp_id,
                    scenario_name=scenario_name,
                    seed=seed,
                    bag_volume_multiplier=multiplier,
                    additional_jams=scenario_def["additional_jams"],
                    foreign_object_scenarios=scenario_def["foreign_object_scenarios"],
                    notes=f"Repeat {repeat+1}/{repeats}"
                )

                print(f"\nRunning: {exp_id}")
                try:
                    evaluator = run_experiment(config, layout_path, base_scenario_path, output_dir)
                    summary = evaluator.get_summary()
                    results.append(summary)
                    print(f"  Completed: {summary.delivered_bags}/{summary.total_bags} delivered, "
                          f"{summary.misrouted_bags} misrouted, {summary.mean_delivery_latency:.1f} avg latency")
                except Exception as e:
                    print(f"  ERROR: {e}")
                    import traceback
                    traceback.print_exc()

    print(f"\n{'=' * 60}")
    print(f"EXPERIMENT SUITE COMPLETED")
    print(f"Total runs: {len(results)}")
    print(f"Results saved to: {output_dir}")
    print(f"{'=' * 60}")

    return results


def run_comparison_suite(
    scenario_names: List[str],
    seeds: List[int] = None,
    repeats: int = 1,
    output_dir: Path = None,
    bag_multipliers: Dict[str, float] = None
):
    """Run comparison suite: both baseline and optimized on same scenarios."""
    if output_dir is None:
        output_dir = BASE_DIR / "experiment_output" / f"comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    if seeds is None:
        seeds = [42, 123, 456, 789, 999]

    if bag_multipliers is None:
        bag_multipliers = {}

    layout_path = BASE_DIR / "data" / "network_layout.json"
    base_scenario_path = BASE_DIR / "data" / "simulation_scenario.json"

    print(f"=" * 60)
    print(f"COMPARISON EXPERIMENT SUITE STARTED")
    print(f"Output directory: {output_dir}")
    print(f"Scenarios: {scenario_names}")
    print(f"Seeds: {seeds}")
    print(f"Repeats per seed: {repeats}")
    print(f"Modules: baseline vs optimized")
    print(f"=" * 60)

    all_results = []

    for scenario_name in scenario_names:
        if scenario_name not in SCENARIOS:
            print(f"WARNING: Unknown scenario '{scenario_name}', skipping")
            continue

        scenario_def = SCENARIOS[scenario_name]
        multiplier = bag_multipliers.get(scenario_name, scenario_def["bag_volume_multiplier"])

        for seed in seeds:
            for repeat in range(repeats):
                exp_id = f"{scenario_name}_seed{seed}_rep{repeat+1}_{uuid.uuid4().hex[:8]}"

                config = ExperimentConfig(
                    experiment_id=exp_id,
                    scenario_name=scenario_name,
                    seed=seed,
                    bag_volume_multiplier=multiplier,
                    additional_jams=scenario_def["additional_jams"],
                    foreign_object_scenarios=scenario_def["foreign_object_scenarios"],
                    notes=f"Repeat {repeat+1}/{repeats}"
                )

                print(f"\nRunning comparison: {exp_id}")
                try:
                    results = run_comparison_experiment(config, layout_path, base_scenario_path, output_dir)

                    # Calculate improvements
                    baseline = results["baseline"]["summary"]
                    optimized = results["optimized"]["summary"]

                    improvement = {
                        "experiment_id": exp_id,
                        "scenario_name": scenario_name,
                        "seed": seed,
                        "repeat": repeat + 1,
                        "baseline_delivered": baseline.delivered_bags,
                        "optimized_delivered": optimized.delivered_bags,
                        "delivered_improvement": optimized.delivered_bags - baseline.delivered_bags,
                        "baseline_misrouted": baseline.misrouted_bags,
                        "optimized_misrouted": optimized.misrouted_bags,
                        "misrouted_reduction": baseline.misrouted_bags - optimized.misrouted_bags,
                        "baseline_latency": baseline.mean_delivery_latency,
                        "optimized_latency": optimized.mean_delivery_latency,
                        "latency_improvement": baseline.mean_delivery_latency - optimized.mean_delivery_latency,
                        "baseline_jams": baseline.total_jams_triggered,
                        "optimized_jams": optimized.total_jams_triggered,
                    }
                    all_results.append(improvement)

                    print(f"  IMPROVEMENT: +{improvement['delivered_improvement']} delivered, "
                          f"{improvement['misrouted_reduction']} fewer misrouted, "
                          f"{improvement['latency_improvement']:.1f} lower latency")

                except Exception as e:
                    print(f"  ERROR: {e}")
                    import traceback
                    traceback.print_exc()

    # Export comparison summary
    comparison_path = output_dir / "comparison_summary.csv"
    if all_results:
        with open(comparison_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=all_results[0].keys())
            writer.writeheader()
            writer.writerows(all_results)
        print(f"\n  Comparison summary exported to: {comparison_path}")

    print(f"\n{'=' * 60}")
    print(f"COMPARISON SUITE COMPLETED")
    print(f"Total comparisons: {len(all_results)}")
    print(f"Results saved to: {output_dir}")
    print(f"{'=' * 60}")

    return all_results


if __name__ == "__main__":
    # Run comparison experiment to show improvements
    print("Running COMPARISON experiment (baseline vs optimized)...")

    layout_path = BASE_DIR / "data" / "network_layout.json"
    base_scenario_path = BASE_DIR / "data" / "simulation_scenario.json"
    output_dir = BASE_DIR / "experiment_output" / "comparison_demo"

    # Run comparison on key scenarios
    run_comparison_suite(
        scenario_names=["baseline", "high_demand", "conveyor_failures", "congestion", "combined_stress"],
        seeds=[42, 123],
        repeats=1,
        output_dir=output_dir
    )