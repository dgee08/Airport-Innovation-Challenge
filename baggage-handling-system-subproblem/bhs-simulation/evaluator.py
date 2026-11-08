import json
import csv
import sys
from pathlib import Path

# Global Simulation Constants
CONGESTION_PENALTY = 2  # Ticks added per active bag sharing the edge
WEAR_JAM_DURATION = 20  # How long a wear-and-tear overload jam lasts
BASE_DIR = Path(__file__).resolve().parent

# Diversion Configuration (can be overridden by scenario)
DEFAULT_DIVERSION_THRESHOLD = 0.7
DEFAULT_DIVERSION_CAPACITY = 50
DEFAULT_DIVERSION_NODE = "DIVERSION_INSPECTION"

class BaggageEvaluator:
    def __init__(self, layout_path, scenario_path):
        self.layout_path = layout_path
        self.scenario_path = scenario_path

        # Load JSON configurations
        with open(layout_path, 'r') as f:
            self.layout = json.load(f)
        with open(scenario_path, 'r') as f:
            self.scenario = json.load(f)

        self.total_ticks = self.scenario["simulation"]["total_ticks"]

        # Diversion configuration from scenario (with defaults)
        diversion_config = self.scenario.get("diversion", {})
        self.diversion_threshold = diversion_config.get("threshold", DEFAULT_DIVERSION_THRESHOLD)
        self.diversion_capacity = diversion_config.get("capacity", DEFAULT_DIVERSION_CAPACITY)
        self.diversion_node = diversion_config.get("node", DEFAULT_DIVERSION_NODE)

        # State Tracking Systems
        self.edge_states = {}
        self.active_bags = {}
        self.completed_bags = {}
        self.current_tick = 0

        # Diversion tracking
        self.diverted_bags = {}  # bag_id -> {diversion_tick, from_node, risk_score, original_destination}
        self.diversion_current_count = 0

        # Setup tracking logs
        self.dhs_log_data = []
        self.bag_log_data = []

        self._initialize_topology()

    def _initialize_topology(self):
        """Builds internal runtime state tracking for nodes and edges, splitting 
        bidirectional lines into independent, parallel physical conveyors."""
        for edge in self.layout["edges"]:
            edge_id = edge["id"]
            is_bidirectional = edge.get("bidirectional", False)
            
            if is_bidirectional:
                # Create Forward Physical Conveyor Line
                fwd_id = f"{edge_id}_FWD"
                self.edge_states[fwd_id] = {
                    "id": fwd_id,
                    "base_id": edge_id,
                    "from": edge["from"],
                    "to": edge["to"],
                    "base_cost": edge["base_cost"],
                    "wear_threshold": edge["wear_threshold"],
                    "status": "OPERATIONAL",
                    "fault_reason": "NONE",
                    "jam_expiry_tick": -1,
                    "cumulative_bags": 0,
                    "active_bag_ids": set()
                }
                # Create Reverse Physical Conveyor Line
                rev_id = f"{edge_id}_REV"
                self.edge_states[rev_id] = {
                    "id": rev_id,
                    "base_id": edge_id,
                    "from": edge["to"],
                    "to": edge["from"],
                    "base_cost": edge["base_cost"],
                    "wear_threshold": edge["wear_threshold"],
                    "status": "OPERATIONAL",
                    "fault_reason": "NONE",
                    "jam_expiry_tick": -1,
                    "cumulative_bags": 0,
                    "active_bag_ids": set()
                }
            else:
                self.edge_states[edge_id] = {
                    "id": edge_id,
                    "base_id": edge_id,
                    "from": edge["from"],
                    "to": edge["to"],
                    "base_cost": edge["base_cost"],
                    "wear_threshold": edge["wear_threshold"],
                    "status": "OPERATIONAL",
                    "fault_reason": "NONE",
                    "jam_expiry_tick": -1,
                    "cumulative_bags": 0,
                    "active_bag_ids": set()
                }

    def _get_active_bags_on_edge(self, edge_id):
        """Returns the total bags occupying this specific directed conveyor belt."""
        return len(self.edge_states[edge_id]["active_bag_ids"])

    def _process_jams(self):
        """Orchestrates scheduled timeline jams and clears expired faults."""
        # 1. Handle Scheduled Jams from JSON scenario
        for jam in self.scenario.get("jams", []):
            if jam["start_tick"] == self.current_tick:
                edge_id = jam["edge_id"]
                self._apply_jam(edge_id, jam["duration"], "SCHEDULED_MAINTENANCE")

        # 2. Re-open operational edges whose jam timelines have expired
        for edge_id, edge in self.edge_states.items():
            if edge["status"] == "JAMMED" and self.current_tick >= edge["jam_expiry_tick"]:
                edge["status"] = "OPERATIONAL"
                edge["fault_reason"] = "NONE"
                edge["jam_expiry_tick"] = -1

    def _apply_jam(self, target_id, duration, reason):
        """Flips an edge to jammed. If a scheduled jam targets a base corridor ID, 
        both the forward and reverse lines shut down for maintenance."""
        for e_id, edge in self.edge_states.items():
            if e_id == target_id or edge.get("base_id") == target_id:
                edge["status"] = "JAMMED"
                edge["fault_reason"] = reason
                edge["jam_expiry_tick"] = self.current_tick + duration

    def _spawn_baggage(self):
        """Injects new baggage into entry ports at their scheduled release tick."""
        for bag_data in self.scenario.get("bags", []):
            if bag_data["release_tick"] == self.current_tick:
                bag_id = bag_data["bag_id"]
                intake = bag_data["intake_node"]
                
                # Find the initial intake feed edge connected to this intake port
                starting_edge_id = None
                for edge_id, edge in self.edge_states.items():
                    if edge["from"] == intake:
                        starting_edge_id = edge_id
                        break
                        
                if not starting_edge_id:
                    raise ValueError(f"Hard Failure: Intake node {intake} has no valid out-edges.")
                
                # Initialize active tracking state
                self.active_bags[bag_id] = {
                    "bag_id": bag_id,
                    "destination_gate": bag_data["destination_gate"],
                    "deadline_tick": bag_data.get("deadline_tick", None),
                    "release_tick": self.current_tick,
                    "current_edge": starting_edge_id,
                    "current_node": intake,
                    "ticks_remaining": self.edge_states[starting_edge_id]["base_cost"],
                    "history": [(intake, self.current_tick)]
                }
                
                # Register bag onto the physical belt
                self.edge_states[starting_edge_id]["active_bag_ids"].add(bag_id)
                self.edge_states[starting_edge_id]["cumulative_bags"] += 1

    def _advance_physics(self):
        """Decrements traversal timers for all bags currently moving on active lines."""
        for bag_id, bag in list(self.active_bags.items()):
            edge_id = bag["current_edge"]
            
            # If the line is jammed, the physical belt halts; the bag freezes in place
            if self.edge_states[edge_id]["status"] == "JAMMED":
                continue
                
            bag["ticks_remaining"] -= 1

    def _get_diversion_edges_from_node(self, node_id):
        """Returns list of diversion edge IDs available from a node."""
        diversion_edges = []
        for edge_id, edge in self.edge_states.items():
            if edge["from"] == node_id and edge.get("base_id", "").startswith("e_") and "_DIVERSION" in edge.get("base_id", ""):
                diversion_edges.append(edge_id)
        # Also check base edges for diversion flag
        for edge in self.layout["edges"]:
            if edge.get("diversion", False) and edge["from"] == node_id:
                # Find the corresponding edge_state
                for e_id, e_state in self.edge_states.items():
                    if e_state.get("base_id") == edge["id"]:
                        diversion_edges.append(e_id)
        return diversion_edges

    def _compute_suspicion_score(self, bag, current_node):
        """Computes real-time suspicion score (0.0-1.0) for a bag at a decision point."""
        score = 0.0

        # Heuristic 1: Cross-terminal routing (higher suspicion)
        bag_dest = bag["destination_gate"]
        bag_intake = bag["history"][0][0] if bag["history"] else ""
        if (bag_intake.startswith("I") and bag_dest.startswith("G")):
            intake_term = bag_intake[1]  # A or B
            dest_term = bag_dest[1]      # A or B
            if intake_term != dest_term:
                score += 0.4

        # Heuristic 2: Repeated node visits (loitering/looping)
        visited_nodes = [n for n, _ in bag["history"]]
        unique_nodes = set(visited_nodes)
        if len(visited_nodes) > len(unique_nodes):
            score += 0.2 * (len(visited_nodes) - len(unique_nodes))

        # Heuristic 3: Deadline proximity (urgent bags less suspicious, very late = suspicious)
        if bag.get("deadline_tick"):
            ticks_to_deadline = bag["deadline_tick"] - self.current_tick
            if ticks_to_deadline < 0:
                score += 0.3
            elif ticks_to_deadline < 10:
                score += 0.1

        # Heuristic 4: Path length anomaly (unusually long paths)
        if len(bag["history"]) > 12:
            score += 0.1 * (len(bag["history"]) - 12)

        # Heuristic 5: Currently at a chokepoint/spine (diversion opportunity)
        chokepoints = {"S2", "S3", "S4"}
        if current_node in chokepoints:
            score += 0.1

        return min(score, 1.0)

    def _is_diversion_available(self, current_node):
        """Checks if diversion track is available from current node."""
        if self.diversion_current_count >= self.diversion_capacity:
            return False
        diversion_edges = self._get_diversion_edges_from_node(current_node)
        for edge_id in diversion_edges:
            edge = self.edge_states[edge_id]
            if edge["status"] == "OPERATIONAL":
                return True
        return False

    def _execute_routing_decisions(self, student_module):
        """Identifies bags that reached choice points and handles student SAC integration."""
        decision_queue = []

        for bag_id, bag in list(self.active_bags.items()):
            if bag["ticks_remaining"] == 0:
                decision_queue.append(bag)

        # CRITICAL: Enforce strict intratick determinism by sorting requests alphabetically
        decision_queue.sort(key=lambda b: b["bag_id"])

        # Build network snapshot arrays to feed student parameters safely
        active_faults = [e_id for e_id, e in self.edge_states.items() if e["status"] == "JAMMED"]
        edge_occupancy = {e_id: len(e["active_bag_ids"]) for e_id, e in self.edge_states.items()}

        for bag in decision_queue:
            bag_id = bag["bag_id"]
            curr_edge_id = bag["current_edge"]
            curr_node = self.edge_states[curr_edge_id]["to"]
            dest_gate = bag["destination_gate"]

            # Clean up old edge registration
            self.edge_states[curr_edge_id]["active_bag_ids"].discard(bag_id)
            bag["current_node"] = curr_node
            bag["history"].append((curr_node, self.current_tick))

            # Check if bag has successfully docked at its target destination gate
            if curr_node == dest_gate:
                bag["arrival_tick"] = self.current_tick
                self.completed_bags[bag_id] = bag
                del self.active_bags[bag_id]
                continue

            # Check if bag was diverted and reached inspection node
            if curr_node == self.diversion_node:
                bag["arrival_tick"] = self.current_tick
                bag["diverted"] = True
                self.completed_bags[bag_id] = bag
                del self.active_bags[bag_id]
                self.diversion_current_count = max(0, self.diversion_current_count - 1)
                continue

            # Compute suspicion score and diversion availability
            suspicion_score = self._compute_suspicion_score(bag, curr_node)
            diversion_available = self._is_diversion_available(curr_node)

            # Execute Student Routing logic via SAC API Hook
            try:
                next_node = student_module.route_bag(
                    bag_id=bag_id,
                    current_node=curr_node,
                    destination_gate=dest_gate,
                    active_faults=list(active_faults),
                    edge_occupancy=dict(edge_occupancy),
                    suspicion_score=suspicion_score,
                    diversion_available=diversion_available,
                    diversion_node=self.diversion_node
                )
            except Exception as e:
                print(f"Hard Failure: Student SAC script crashed at tick {self.current_tick} on bag {bag_id}. Error: {e}")
                sys.exit(1)

            # Validate connection integrity (Anti-Teleportation Enforcement)
            chosen_edge_id = None
            for edge_id, edge in self.edge_states.items():
                if edge["from"] == curr_node and edge["to"] == next_node:
                    chosen_edge_id = edge_id
                    break

            if not chosen_edge_id:
                print(f"Hard Failure: Invalid Route Choice! Node '{curr_node}' does not connect to '{next_node}'.")
                sys.exit(1)

            # Check if this is a diversion decision
            is_diversion = (next_node == self.diversion_node)
            if is_diversion:
                self.diverted_bags[bag_id] = {
                    "diversion_tick": self.current_tick,
                    "from_node": curr_node,
                    "risk_score": suspicion_score,
                    "original_destination": dest_gate
                }
                self.diversion_current_count += 1
                # Log diversion event (for ExperimentEvaluator)
                if hasattr(self, '_log_diversion'):
                    self._log_diversion(bag_id, curr_node, suspicion_score, dest_gate)

            # Assign bag onto its new conveyor pathway
            target_edge = self.edge_states[chosen_edge_id]
            target_edge["active_bag_ids"].add(bag_id)
            target_edge["cumulative_bags"] += 1

            # Check dynamic wear-and-tear degradation triggers (only jams this specific direction)
            if target_edge["cumulative_bags"] >= target_edge["wear_threshold"] and target_edge["status"] == "OPERATIONAL":
                self._apply_jam(chosen_edge_id, WEAR_JAM_DURATION, "MECHANICAL_OVERLOAD")

            # Compute runtime congestion and assign traversal ticks
            current_sharing_count = self._get_active_bags_on_edge(chosen_edge_id)
            effective_cost = target_edge["base_cost"] + (current_sharing_count * CONGESTION_PENALTY)

            bag["current_edge"] = chosen_edge_id
            bag["ticks_remaining"] = effective_cost
            bag["suspicion_score"] = suspicion_score
            bag["diverted"] = is_diversion

            # Update local tracking snapshots for subsequent loops inside this same tick
            edge_occupancy[chosen_edge_id] = len(target_edge["active_bag_ids"])

    def _log_dhs_telemetry(self):
        """Appends snapshots to the DHS analytics buffer array every tick."""
        for edge_id, edge in self.edge_states.items():
            self.dhs_log_data.append({
                "tick": self.current_tick,
                "edge_id": edge_id,
                "status": edge["status"],
                "fault_reason": edge["fault_reason"],
                "active_bags": len(edge["active_bag_ids"]),
                "cumulative_volume": edge["cumulative_bags"]
            })

        # Log per-bag positions for real-time dashboard KPIs
        for bag_id, bag in self.active_bags.items():
            self.bag_log_data.append({
                "tick": self.current_tick,
                "bag_id": bag_id,
                "current_edge": bag["current_edge"],
                "current_node": bag["current_node"],
                "ticks_remaining": bag["ticks_remaining"],
                "arrival_tick": "",
                "destination_gate": bag["destination_gate"],
                "release_tick": bag["release_tick"],
                "deadline_tick": bag.get("deadline_tick", "") or "",
                "suspicion_score": bag.get("suspicion_score", 0.0),
                "diverted": bag.get("diverted", False),
                "diversion_tick": bag.get("diversion_tick", "") or ""
            })

        # Log completed bags at their arrival tick (so dashboard knows they delivered)
        for bag_id, bag in self.completed_bags.items():
            if bag["arrival_tick"] == self.current_tick:
                is_diverted = bag.get("diverted", False)
                diversion_info = self.diverted_bags.get(bag_id, {})
                self.bag_log_data.append({
                    "tick": self.current_tick,
                    "bag_id": bag_id,
                    "current_edge": "",
                    "current_node": self.diversion_node if is_diverted else bag["destination_gate"],
                    "ticks_remaining": 0,
                    "arrival_tick": bag["arrival_tick"],
                    "destination_gate": bag["destination_gate"],
                    "release_tick": bag["release_tick"],
                    "deadline_tick": bag.get("deadline_tick", "") or "",
                    "suspicion_score": bag.get("suspicion_score", 0.0),
                    "diverted": is_diverted,
                    "diversion_tick": diversion_info.get("diversion_tick", "") or ""
                })

    def export_logs(self, output_path=BASE_DIR / "live_telemetry.csv"):
        """Dumps internal DHS time-series tracking variables to disk."""
        if not self.dhs_log_data:
            return
        keys = self.dhs_log_data[0].keys()
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(self.dhs_log_data)
        print(f"DHS Step Complete: Telemetry successfully exported to '{output_path}'.")

    def export_bag_logs(self, output_path=BASE_DIR / "live_bag_telemetry.csv"):
        """Dumps per-bag position tracking to disk for real-time dashboard KPIs."""
        if not self.bag_log_data:
            return
        keys = self.bag_log_data[0].keys()
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(self.bag_log_data)
        print(f"DHS Step Complete: Bag telemetry exported to '{output_path}'.")

    def run(self, student_module):
        """Main execution engine processing the 1-350 tick timeline loop."""
        print(f"Initializing SmartSort Evaluation Simulation Loop ({self.total_ticks} Ticks)...")
        for tick in range(1, self.total_ticks + 1):
            self.current_tick = tick
            self._process_jams()
            self._spawn_baggage()
            self._advance_physics()
            self._execute_routing_decisions(student_module)
            self._log_dhs_telemetry()

        self.export_logs()
        self.export_bag_logs()
        self._calculate_final_scores()

    def _calculate_final_scores(self):
        """Computes metrics to evaluate the performance of student code configurations."""
        total_bags = len(self.scenario["bags"])
        delivered_count = len(self.completed_bags)
        stranded_count = len(self.active_bags)

        # Count diverted bags separately
        diverted_count = sum(1 for bag in self.completed_bags.values() if bag.get("diverted", False))
        normal_delivered = delivered_count - diverted_count

        misrouted_count = 0
        total_transit_time = 0

        for bag_id, bag in self.completed_bags.items():
            transit_time = bag["arrival_tick"] - bag["release_tick"]
            total_transit_time += transit_time

            if bag["deadline_tick"] and bag["arrival_tick"] > bag["deadline_tick"]:
                misrouted_count += 1

        # Stranded items automatically log as failed delivery window breaches
        misrouted_count += stranded_count
        mean_transit_time = (total_transit_time / delivered_count) if delivered_count > 0 else 0

        print("\n" + "="*40)
        print("          SMARTSORT SIMULATION SCORE")
        print("="*40)
        print(f"Total Scenario Baggage : {total_bags}")
        print(f"Successfully Delivered : {delivered_count} (Normal: {normal_delivered}, Diverted: {diverted_count})")
        print(f"Stranded on Belts      : {stranded_count}")
        print(f"Total Misrouted Bags   : {misrouted_count}  (Lower is better)")
        print(f"Mean Transit Time      : {mean_transit_time:.2f} ticks (Lower is better)")
        print("="*40 + "\n")

if __name__ == "__main__":
    import solution

    evaluator = BaggageEvaluator(
        layout_path=BASE_DIR / "data" / "network_layout.json",
        scenario_path=BASE_DIR / "data" / "simulation_scenario.json"
    )
    evaluator.run(solution)