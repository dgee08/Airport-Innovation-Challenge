# BaggageIQ: Baggage Handling Optimization & Monitoring

**Airport Innovation Challenge — Baggage Handling System Subproblem**

![BaggageIQ Dashboard](baggage-handling-system-subproblem/assets/BaggageIQDashboard.png)

BaggageIQ is a Python-based simulation and monitoring project that explores how improved routing algorithms and operational analytics can improve airport baggage handling. The project replaces a basic Breadth-First Search (BFS) routing approach with a weighted Dijkstra algorithm that accounts for conveyor congestion, equipment faults, wear, and baggage delivery deadlines.

The system also includes suspicious baggage detection, an interactive monitoring dashboard, and a simulation experiment framework for comparing routing performance across different operating conditions.

## Project Highlights

- **Routing Optimization:** Implemented weighted Dijkstra pathfinding to account for conveyor occupancy, active jams, equipment wear, and downstream congestion.
- **Suspicious Baggage Detection:** Developed rule-based scoring to identify unusual baggage routing patterns and divert flagged bags to a simulated inspection station.
- **Operational Dashboard:** Built an interactive Tkinter dashboard for monitoring conveyor status, baggage movement, system incidents, and key performance indicators.
- **Simulation Experiments:** Developed a configurable experiment runner to compare baseline and optimized routing across multiple scenarios and random seeds.
- **Data Analytics & Export:** Automated the generation of structured CSV datasets for baggage-level, conveyor-level, and incident-level analysis in Python and Power BI.

## Performance Evaluation

The experiment framework compares the original BFS algorithm against the upgraded Dijkstra implementation under identical simulated scenarios.

The following results are from the sample comparison output:

| Scenario | Baseline Misrouted | Optimized Misrouted | Reduction |
|---|---:|---:|---:|
| Baseline | 193 | 71 | 63.2% |
| High Demand | 218 | 104 | 52.3% |
| Conveyor Failures | 260 | 127 | 51.2% |
| Congestion | 284 | 149 | 47.5% |
| Combined Stress | 316 | 193 | 38.9% |

The sample results show fewer reported misrouted bags with the upgraded routing algorithm across all five scenarios. Performance varies under different operating conditions, with the combined-stress scenario presenting the greatest challenge.

*Results are simulation outputs, not measurements from a deployed airport baggage handling system. They should be interpreted in the context of the simulated network, scenario configuration, and experiment settings.*

## Key Features

### 1. Weighted Dijkstra Routing

Replaced the baseline BFS approach, which prioritizes the number of edges traversed, with a weighted Dijkstra algorithm that evaluates the operational cost of different routes.

The routing algorithm considers:

- Base conveyor travel cost.
- Current conveyor occupancy and congestion penalties.
- Active equipment faults and jam penalties.
- Cumulative conveyor volume and wear-related penalties.
- Estimated congestion on downstream edges.
- Baggage delivery deadlines and urgency levels.

This allows the routing system to evaluate alternatives based on more than simply finding the shortest path.

### 2. Suspicious Baggage Detection & Diversion

Implemented a rule-based detection mechanism that assigns suspicion scores based on simulated baggage movement patterns.

Detection heuristics include:

- Unusual cross-terminal routing.
- Repeated visits to the same nodes.
- Excessive route length or number of hops.
- Missed or approaching delivery deadlines.
- Movement through designated network chokepoints.

Bags exceeding the configured suspicion threshold can be directed to a simulated inspection station, subject to available inspection capacity.

### 3. Interactive Monitoring Dashboard

Developed a Tkinter dashboard that provides a visual representation of the simulated baggage network and its operational state.

Dashboard capabilities include:

- Network topology visualization with conveyor and node status indicators.
- KPI monitoring for delivered, misrouted, in-transit, suspicious, and diverted bags.
- Filterable incident and alert logs.
- Conveyor and baggage inspection panels with historical information.
- Playback controls for examining simulation events over time.
- Visual indicators for congestion, jams, suspicious baggage, and simulated foreign-object incidents.

The dashboard uses recorded simulation telemetry and playback controls; it is not connected to a live airport conveyor network.

### 4. Simulation & Experiment Framework

Created an experiment runner to evaluate routing performance under different operating conditions.

Supported scenarios include:

- Baseline operations.
- High baggage demand.
- Conveyor failures.
- Increased congestion.
- Simulated foreign objects.
- Suspicious baggage.
- Combined stress conditions.

The framework supports baseline-versus-optimized comparisons, configurable random seeds, repeated runs, and automated result exports.

## Data & Analytics

The experiment framework generates structured CSV files that can be used for further analysis and visualization.

| Dataset | Description | Example Fields |
|---|---|---|
| `simulation_summary.csv` | Run-level performance metrics | Delivered bags, misrouted bags, average latency, total jams |
| `bag_details.csv` | Individual baggage journey summaries | Origin, destination, route, delivery time, misrouting status, number of hops |
| `track_performance.csv` | Conveyor-level performance data | Tick, edge ID, status, active bags, cumulative volume |
| `incident_log.csv` | Recorded simulation incidents | Tick, incident type, severity, location, duration |

These datasets support analysis of:

- Routing performance across different scenarios.
- Baggage delivery times and deadline performance.
- Conveyor utilization and congestion patterns.
- Incident frequency and duration.
- Differences between baseline and optimized routing.

During our presentation, I used simulation_summary to make Power BI graphs.

## Technology Stack

| Technology | Application |
|---|---|
| **Python** | Simulation logic, routing algorithms, experiment automation, and data processing |
| **Tkinter** | Interactive baggage monitoring dashboard |
| **Power BI** | Performance visualization and scenario comparisons |
| **CSV** | Structured experiment outputs and telemetry storage |
| **JSON** | Network topology and simulation scenario configuration |

## Project Structure

```text
bhs-simulation/
├── oursolution.py          # Optimized Dijkstra routing algorithm
├── solution.py             # Baseline BFS routing algorithm
├── evaluator.py            # Simulation engine and routing evaluation
├── bsd_dashboard.py        # Interactive monitoring dashboard
├── experiment_runner.py    # Scenario experiments and CSV exports
├── generate_scenario.py    # Simulation scenario generation
├── data/
│   ├── network_layout.json
│   └── simulation_scenario.json
├── analysis/
│   ├── analysiswork.py     # Data analysis and post-processing
│   └── load_data.py        # Data loading utilities
├── experiment_output/      # Generated experiment results
└── dashboard_cache/        # Cached simulation telemetry
```

## Getting Started

### Prerequisites

- Python 3.10+
- Tkinter (typically included with standard Python installations)

### Run the Simulation

```bash
python evaluator.py
```

### Launch the Dashboard

```bash
python bsd_dashboard.py
```

The dashboard supports selecting a simulation scenario and routing solution, running the simulation, and examining its recorded telemetry through playback controls.

### Run a Baseline vs. Optimized Comparison

```python
from experiment_runner import run_comparison_suite
from pathlib import Path

run_comparison_suite(
    scenario_names=[
        "baseline",
        "high_demand",
        "conveyor_failures",
        "congestion",
        "combined_stress"
    ],
    seeds=[42, 123],
    repeats=2,
    output_dir=Path("experiment_output/comparison")
)
```

Generated CSV files are saved in the specified output directory.

## Future Improvements

- Integrate machine learning for baggage anomaly detection and demand forecasting.
- Expand performance analysis to include energy consumption and maintenance costs.
- Connect the simulation to real-world baggage handling telemetry.
- Develop a web-based dashboard for broader operational accessibility.