"""
Airport Innovation Challenge - BaggageIQ: Smart Baggage Handling Dashboard
Operator-Grade Baggage Handling Control-Room Dashboard

Features:
- Network visualization with topological layout
- KPI panel with real-time metrics
- Alert/event log with severity classification
- Track/Bag inspector with detailed telemetry
- Playback controls (play/pause, speed, step, scrub, jump-to-event)
- Suspicious bag detection (anomalous routing, stuck bags, cross-terminal anomalies)
- Foreign-object detection (simulated incidents with proper lifecycle)
- Dark control-room theme with professional industrial styling
"""

import tkinter as tk
from tkinter import ttk, messagebox
import csv
import os
import sys
import json
import math
import threading
import uuid
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict
from enum import Enum

BASE_DIR = Path(__file__).resolve().parent

# Import experiment runner for scenario definitions and running
sys.path.insert(0, str(BASE_DIR))
from experiment_runner import SCENARIOS, run_experiment, ExperimentConfig, BASE_DIR as EXP_BASE_DIR
from evaluator import BaggageEvaluator
import solution
import oursolution

# =============================================================================
# CONSTANTS & CONFIGURATION
# =============================================================================

NODE_COORDINATES = {
    "IA1": (100, 140), "IA2": (100, 280),
    "JA1": (280, 140), "JA2": (460, 140), "JA3": (640, 140), "JA4": (820, 140), "JA5": (550, 60),
    "GA1": (280, 40),  "GA2": (460, 40),  "GA3": (640, 40),  "GA4": (820, 40),
    "S1": (280, 420),  "S2": (460, 420),  "S3": (640, 420), "S4": (820, 420), "S5": (1000, 420), "S6": (640, 540),
    "IB1": (100, 660), "IB2": (100, 540),
    "JB1": (280, 660), "JB2": (460, 660), "JB3": (640, 660), "JB4": (820, 660), "JB5": (550, 720),
    "GB1": (1000, 140), "GB2": (1000, 260), "GB3": (1000, 540), "GB4": (1000, 660),
    "DIVERSION_INSPECTION": (640, 280)
}

NODE_RADIUS = 16
SUB_FRAMES_PER_TICK = 10
REFRESH_RATE_MS = 16

# Color Palette - Control Room Theme
class Colors:
    BG_DEEP = "#0a0a0d"
    BG_PANEL = "#111115"
    BG_CARD = "#16161d"
    BG_CANVAS = "#0e0e12"
    FG_PRIMARY = "#e8e8ec"
    FG_SECONDARY = "#a3a3af"
    FG_MUTED = "#787886"
    ACCENT_CYAN = "#00d4aa"
    ACCENT_BLUE = "#3b82f6"
    ACCENT_ORANGE = "#f59e0b"
    ACCENT_RED = "#ef4444"
    ACCENT_PURPLE = "#a855f7"
    ACCENT_GREEN = "#26bc5d"
    ACCENT_AMBER = "#fbbf24"

    # State colors
    IDLE = "#1e293b"
    OCCUPIED_LOW = "#1e3a5f"
    OCCUPIED_MED = "#1e4d7a"
    OCCUPIED_HIGH = "#2d5a27"
    CONGESTED = "#7c2d12"
    JAMMED = "#7f1d1d"
    DISABLED = "#3f3f46"
    SUSPICIOUS = "#7c2d92"
    FOREIGN_OBJECT = "#92400e"
    DIVERSION = "#fbbf24"

    # Severity
    SEV_INFO = "#3b82f6"
    SEV_WARNING = "#f59e0b"
    SEV_CRITICAL = "#ef4444"
    SEV_EMERGENCY = "#dc2626"

    # Node types
    INTAKE = "#1e3a5f"
    JUNCTION = "#374151"
    SPINE = "#4c1d95"
    GATE = "#14532d"
    CROSS_TERMINAL = "#7c2d12"
    INSPECTION = "#fbbf24"

# Node type classification
NODE_TYPES = {
    "IA1": "intake", "IA2": "intake", "IB1": "intake", "IB2": "intake",
    "JA1": "junction", "JA2": "junction", "JA3": "junction", "JA4": "junction", "JA5": "junction",
    "JB1": "junction", "JB2": "junction", "JB3": "junction", "JB4": "junction", "JB5": "junction",
    "S1": "spine", "S2": "spine", "S3": "spine", "S4": "spine", "S5": "spine", "S6": "spine",
    "GA1": "gate", "GA2": "gate", "GA3": "gate", "GA4": "gate",
    "GB1": "gate", "GB2": "gate", "GB3": "gate", "GB4": "gate",
    "DIVERSION_INSPECTION": "inspection"
}

NODE_TYPE_COLORS = {
    "intake": Colors.INTAKE,
    "junction": Colors.JUNCTION,
    "spine": Colors.SPINE,
    "gate": Colors.GATE,
    "inspection": Colors.INSPECTION
}

NODE_TYPE_LABELS = {
    "intake": "INTAKE",
    "junction": "JUNCTION",
    "spine": "SPINE",
    "gate": "GATE",
    "inspection": "INSPECTION"
}

# Scenario phases
PHASES = [
    {"name": "warm_up", "label": "WARM-UP", "start": 1, "end": 300, "color": "#1e40af"},
    {"name": "first_pressure", "label": "FIRST PRESSURE", "start": 301, "end": 900, "color": "#3b82f6"},
    {"name": "sustained_load", "label": "SUSTAINED LOAD", "start": 901, "end": 2100, "color": "#f59e0b"},
    {"name": "crisis_peak", "label": "CRISIS PEAK", "start": 2101, "end": 3000, "color": "#ef4444"},
    {"name": "wind_down", "label": "WIND-DOWN", "start": 3001, "end": 3600, "color": "#22c55e"}
]

# Edge connections for network topology
EDGE_CONNECTIONS = [
    # Terminal A intake feeds
    ("IA1", "JA1"), ("IA1", "JA2"), ("IA2", "JA3"), ("IA2", "JA4"),
    # Terminal B intake feeds
    ("IB1", "JB1"), ("IB1", "JB2"), ("IB2", "JB3"), ("IB2", "JB4"),
    # Terminal A junction internal
    ("JA1", "JA2"), ("JA2", "JA3"), ("JA3", "JA4"), ("JA3", "JA5"), ("JA5", "JA2"),
    # Terminal B junction mesh
    ("JB1", "JB2"), ("JB1", "JB3"), ("JB4", "JB3"), ("JB2", "JB5"), ("JB3", "JB5"), ("JB4", "JB5"),
    # Junction to spine
    ("JA1", "S1"), ("JA2", "S2"), ("JA3", "S3"), ("JA4", "S3"), ("JA5", "S2"),
    ("JB1", "S4"), ("JB2", "S4"), ("JB3", "S5"), ("JB4", "S6"), ("JB5", "S4"),
    # Cross terminal
    ("JA1", "JB1"),
    # Spine trunk
    ("S1", "S2"), ("S2", "S3"), ("S3", "S4"), ("S4", "S5"),
    # Detour belts
    ("S1", "S6"), ("S6", "S5"),
    # Gate feeds A
    ("S1", "GA1"), ("S1", "GA2"), ("S2", "GA2"), ("S2", "GA3"), ("S3", "GA3"), ("S3", "GA4"),
    # Gate feeds B
    ("S4", "GB1"), ("S4", "GB2"), ("S5", "GB2"), ("S5", "GB3"), ("S6", "GB3"), ("S6", "GB4"),
    # Diversion tracks
    ("S2", "DIVERSION_INSPECTION"), ("S3", "DIVERSION_INSPECTION"), ("S4", "DIVERSION_INSPECTION")
]

# Bidirectional edges
BIDIRECTIONAL_EDGES = {
    ("JA1", "JB1"), ("JB1", "JA1"),
    ("S2", "S3"), ("S3", "S2"),
    ("S1", "S6"), ("S6", "S1"),
    ("S6", "S5"), ("S5", "S6")
}

# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class TelemetryRecord:
    tick: int
    edge_id: str
    status: str
    fault_reason: str
    active_bags: int
    cumulative_volume: int

@dataclass
class BagInfo:
    bag_id: str
    intake_node: str
    destination_gate: str
    release_tick: int
    deadline_tick: Optional[int] = None
    current_node: Optional[str] = None
    current_edge: Optional[str] = None
    history: List[Tuple[str, int]] = field(default_factory=list)
    arrival_tick: Optional[int] = None
    is_suspicious: bool = False
    suspicious_reasons: List[str] = field(default_factory=list)

    @property
    def transit_time(self) -> Optional[int]:
        if self.arrival_tick and self.release_tick:
            return self.arrival_tick - self.release_tick
        return None

    @property
    def is_overdue(self) -> bool:
        if self.deadline_tick and self.arrival_tick:
            return self.arrival_tick > self.deadline_tick
        return False

    @property
    def is_misrouted(self) -> bool:
        if self.deadline_tick and self.arrival_tick:
            return self.arrival_tick > self.deadline_tick
        return False

@dataclass
class AlertEvent:
    tick: int
    track_id: str
    zone: str
    description: str
    severity: str  # INFO, WARNING, CRITICAL, EMERGENCY
    status: str    # ACTIVE, ACKNOWLEDGED, RESOLVED
    event_type: str  # JAM, CONGESTION, SUSPICIOUS_BAG, FOREIGN_OBJECT, WEAR_OVERLOAD, MECHANICAL
    bag_id: Optional[str] = None
    end_tick: Optional[int] = None

@dataclass
class ForeignObjectEvent:
    event_id: str
    track_id: str
    zone: str
    start_tick: int
    end_tick: Optional[int]
    severity: str
    description: str
    object_type: str  # DEBRIS, SPILLAGE, OBSTRUCTION, UNKNOWN
    status: str  # DETECTED, ONGOING, CLEARED

# =============================================================================
# SUSPICIOUS BAG DETECTOR
# =============================================================================

class SuspiciousBagDetector:
    """Detects suspicious baggage patterns by simulating bag routes through the network
    using the same routing logic as the evaluator, combined with telemetry data."""

    def __init__(self, scenario_data: dict, layout_data: dict, telemetry_history: Dict[int, Dict[str, dict]]):
        self.scenario = scenario_data
        self.layout = layout_data
        self.telemetry = telemetry_history
        self.bags: Dict[str, BagInfo] = {}
        self.suspicious_bags: Set[str] = set()
        self.detection_events: List[AlertEvent] = []

        # Build node type lookup
        self.node_types = {n["id"]: n["type"] for n in layout_data["nodes"]}

        # Build adjacency for routing analysis
        self.adjacency = defaultdict(set)
        self.edge_lookup = {}  # (from, to) -> edge_id
        self.edge_base_cost = {}
        self.edge_wear_threshold = {}
        for edge in layout_data["edges"]:
            self.adjacency[edge["from"]].add(edge["to"])
            self.edge_lookup[(edge["from"], edge["to"])] = edge["id"]
            self.edge_base_cost[edge["id"]] = edge["base_cost"]
            self.edge_wear_threshold[edge["id"]] = edge["wear_threshold"]
            if edge.get("bidirectional", False):
                self.adjacency[edge["to"]].add(edge["from"])
                rev_id = f"{edge['id']}_REV"
                self.edge_lookup[(edge["to"], edge["from"])] = rev_id
                self.edge_base_cost[rev_id] = edge["base_cost"]
                self.edge_wear_threshold[rev_id] = edge["wear_threshold"]

        # Jam schedule from scenario
        self.jam_schedule = {}
        for jam in scenario_data.get("jams", []):
            if jam["start_tick"] not in self.jam_schedule:
                self.jam_schedule[jam["start_tick"]] = []
            self.jam_schedule[jam["start_tick"]].append(jam)

        # Initialize bags from scenario
        for bag_data in scenario_data.get("bags", []):
            bag = BagInfo(
                bag_id=bag_data["bag_id"],
                intake_node=bag_data["intake_node"],
                destination_gate=bag_data["destination_gate"],
                release_tick=bag_data["release_tick"],
                deadline_tick=bag_data.get("deadline_tick")
            )
            self.bags[bag.bag_id] = bag

        # Do NOT simulate on init - wait for actual telemetry data
        self.bag_states_per_tick = {}
        self.bag_history_per_tick = {}
        self.precomputed_alerts = defaultdict(list)
        self._simulation_ran = False

    def simulate_with_telemetry(self, telemetry_history: Dict[int, Dict[str, dict]]):
        """Run simulation using actual telemetry data (jams, congestion) from a completed run."""
        if self._simulation_ran and self.telemetry == telemetry_history:
            return  # Already simulated with this telemetry
        self.telemetry = telemetry_history
        self._simulate_all_bag_routes()
        self._simulation_ran = True

    def _simulate_all_bag_routes(self):
        """Simulate all bags through the network to build route histories, per-tick states, and pre-computed alerts."""
        # Track active edges and their states per tick
        edge_states = {}
        for edge_id, cost in self.edge_base_cost.items():
            base_id = edge_id.replace("_FWD", "").replace("_REV", "")
            edge_states[edge_id] = {
                "status": "OPERATIONAL",
                "fault_reason": "NONE",
                "jam_expiry": -1,
                "cumulative": 0,
                "active_bags": set()
            }

        # Per-tick bag states: tick -> {bag_id: (current_node, current_edge, arrival_tick)}
        self.bag_states_per_tick = {}

        # Per-tick bag history snapshots for detection rules needing history
        self.bag_history_per_tick = {}

        # Pre-computed alerts per tick
        self.precomputed_alerts = defaultdict(list)

        # Sort bags by release tick
        sorted_bags = sorted(self.bags.values(), key=lambda b: b.release_tick)

        max_tick = self.scenario["simulation"]["total_ticks"]

        for tick in range(1, max_tick + 1):
            # Process scheduled jams
            if tick in self.jam_schedule:
                for jam in self.jam_schedule[tick]:
                    target = jam["edge_id"]
                    duration = jam["duration"]
                    reason = jam.get("note", "SCHEDULED_MAINTENANCE")
                    for eid in edge_states:
                        if eid == target or eid.replace("_FWD", "").replace("_REV", "") == target:
                            edge_states[eid]["status"] = "JAMMED"
                            edge_states[eid]["fault_reason"] = reason
                            edge_states[eid]["jam_expiry"] = tick + duration

            # Clear expired jams
            for eid, state in edge_states.items():
                if state["status"] == "JAMMED" and tick >= state["jam_expiry"]:
                    state["status"] = "OPERATIONAL"
                    state["fault_reason"] = "NONE"
                    state["jam_expiry"] = -1

            # Spawn new bags
            for bag in sorted_bags:
                if bag.release_tick == tick:
                    # Find starting edge
                    start_edge = None
                    for (u, v), eid in self.edge_lookup.items():
                        if u == bag.intake_node:
                            start_edge = eid
                            break
                    if start_edge:
                        edge_states[start_edge]["active_bags"].add(bag.bag_id)
                        edge_states[start_edge]["cumulative"] += 1
                        bag.current_edge = start_edge
                        bag.current_node = bag.intake_node
                        bag.history.append((bag.intake_node, tick))
                        bag.ticks_remaining = edge_states[start_edge].get("base_cost",
                            self.edge_base_cost.get(start_edge.replace("_FWD", "").replace("_REV", ""), 4))

            # Advance bags on edges
            for bag in sorted_bags:
                if bag.release_tick > tick or bag.arrival_tick is not None:
                    continue
                if not bag.current_edge:
                    continue

                edge_state = edge_states.get(bag.current_edge)
                if not edge_state:
                    continue

                # Check if jammed
                if edge_state["status"] == "JAMMED":
                    continue

                bag.ticks_remaining -= 1

                # Check if arrived at node
                if bag.ticks_remaining <= 0:
                    # Find current node (to-node of current edge)
                    curr_edge_base = bag.current_edge.replace("_FWD", "").replace("_REV", "")
                    for (u, v), eid in self.edge_lookup.items():
                        if eid == bag.current_edge:
                            bag.current_node = v
                            break
                    bag.history.append((bag.current_node, tick))

                    # Check if delivered
                    if bag.current_node == bag.destination_gate:
                        bag.arrival_tick = tick
                        edge_state["active_bags"].discard(bag.bag_id)
                        continue

                    # Route to next node (simplified BFS routing avoiding jams)
                    next_node = self._route_bag(bag.current_node, bag.destination_gate, edge_states)
                    if next_node and next_node != bag.current_node:
                        # Find edge to next node
                        next_edge = self.edge_lookup.get((bag.current_node, next_node))
                        if next_edge:
                            # Check wear overload
                            edge_state_next = edge_states[next_edge]
                            edge_state_next["active_bags"].add(bag.bag_id)
                            edge_state_next["cumulative"] += 1
                            if edge_state_next["cumulative"] >= self.edge_wear_threshold.get(next_edge, 999999) and edge_state_next["status"] == "OPERATIONAL":
                                edge_state_next["status"] = "JAMMED"
                                edge_state_next["fault_reason"] = "MECHANICAL_OVERLOAD"
                                edge_state_next["jam_expiry"] = tick + 20

                            # Compute congestion cost
                            sharing = len(edge_state_next["active_bags"])
                            base_cost = self.edge_base_cost.get(next_edge, 4)
                            bag.ticks_remaining = base_cost + sharing * 2

                            bag.current_edge = next_edge
                            edge_state["active_bags"].discard(bag.bag_id)

            # Capture bag state at this tick
            self.bag_states_per_tick[tick] = {}
            self.bag_history_per_tick[tick] = {}
            for bag in sorted_bags:
                if bag.release_tick <= tick:
                    self.bag_states_per_tick[tick][bag.bag_id] = (
                        bag.current_node,
                        bag.current_edge,
                        bag.arrival_tick
                    )
                    # Store a copy of history up to this tick
                    self.bag_history_per_tick[tick][bag.bag_id] = list(bag.history)

            # Run detection rules at this tick using per-tick state
            self._run_detection_at_tick(tick, edge_states)

    def _route_bag(self, current: str, dest: str, edge_states: dict) -> Optional[str]:
        """Simple BFS routing avoiding jammed edges."""
        if current == dest:
            return current

        queue = [(current, [current])]
        visited = {current}

        while queue:
            node, path = queue.pop(0)
            for neighbor in self.adjacency.get(node, []):
                if neighbor in visited:
                    continue
                # Check if edge is jammed
                edge_id = self.edge_lookup.get((node, neighbor))
                if edge_id and edge_states.get(edge_id, {}).get("status") == "JAMMED":
                    continue
                new_path = path + [neighbor]
                if neighbor == dest:
                    return new_path[1]
                visited.add(neighbor)
                queue.append((neighbor, new_path))
        return None

    def _run_detection_at_tick(self, tick: int, edge_states: dict):
        """Run detection rules using per-tick bag states and history."""
        # Get per-tick data
        tick_states = self.bag_states_per_tick.get(tick, {})
        tick_histories = self.bag_history_per_tick.get(tick, {})

        for bag_id, bag in self.bags.items():
            if bag_id in self.suspicious_bags:
                continue

            # Get per-tick state
            current_node, current_edge, arrival_tick = tick_states.get(bag_id, (None, None, None))
            history = tick_histories.get(bag_id, [])

            # Skip if bag hasn't been released yet
            if bag.release_tick > tick:
                continue

            reasons = []

            # Rule 1: Cross-terminal routing anomaly
            if self._is_cross_terminal_anomaly_at_tick(bag, history, arrival_tick):
                reasons.append("CROSS_TERMINAL_ANOMALY")

            # Rule 2: Bag stalled on jammed/congested edge
            if self._is_stalled_at_tick(bag, history, current_node, current_edge, arrival_tick, tick, edge_states):
                reasons.append("EXCESSIVE_DWELL")

            # Rule 3: Bag visiting loop nodes multiple times
            if self._is_looping_at_tick(history, arrival_tick):
                reasons.append("LOOP_DETECTED")

            # Rule 4: Excessive transit time (delivered bags only)
            if self._is_excessive_transit_at_tick(bag, arrival_tick, tick):
                reasons.append("EXCESSIVE_TRANSIT_TIME")

            # Rule 5: Unusual route (excessive hops)
            if self._is_unusual_route_at_tick(history, arrival_tick):
                reasons.append("UNUSUAL_ROUTE")

            # Rule 6: Wrong direction (back to intake)
            if self._is_wrong_direction_at_tick(history, arrival_tick):
                reasons.append("WRONG_DIRECTION")

            # Rule 7: Missed deadline (misrouted)
            if self._is_missed_deadline_at_tick(bag, arrival_tick, tick):
                reasons.append("MISSED_DEADLINE")

            if reasons:
                self._flag_suspicious(bag, reasons, tick)
                loc = current_node or bag.intake_node
                track_id = current_edge or "UNKNOWN"
                event = AlertEvent(
                    tick=tick,
                    track_id=track_id,
                    zone=self._get_zone(loc),
                    description=f"Suspicious bag: {bag.bag_id} — {'; '.join(reasons)}",
                    severity="WARNING",
                    status="ACTIVE",
                    event_type="SUSPICIOUS_BAG",
                    bag_id=bag.bag_id
                )
                self.precomputed_alerts[tick].append(event)
                self.detection_events.append(event)

    def process_telemetry_tick(self, tick: int, tick_data: Dict[str, dict]) -> List[AlertEvent]:
        """Return pre-computed alerts for this tick."""
        return self.precomputed_alerts.get(tick, [])

    def _is_cross_terminal_anomaly(self, bag: BagInfo) -> bool:
        """Detect cross-terminal bag not using JA1<->JB1 bridge."""
        if not bag.arrival_tick:
            return False
        intake_term = "A" if bag.intake_node.startswith("I") else "B"
        gate_term = "A" if bag.destination_gate.startswith("GA") else "B"
        if intake_term != gate_term:
            for node, _ in bag.history:
                if node in ("JA1", "JB1"):
                    return False
            return True
        return False

    def _is_stalled(self, bag: BagInfo, current_tick: int) -> bool:
        """Detect bags stuck on same node for too long."""
        if bag.arrival_tick is not None or bag.release_tick > current_tick:
            return False
        if len(bag.history) < 2:
            return False
        # Check if stuck at same node for > 30 ticks
        current_node = bag.history[-1][0]
        stuck_ticks = 0
        for node, tick in reversed(bag.history):
            if node == current_node:
                stuck_ticks = current_tick - tick
            else:
                break
        return stuck_ticks > 30

    def _is_looping(self, bag: BagInfo) -> bool:
        """Detect multiple visits to loop trap nodes."""
        if not bag.arrival_tick:
            return False
        loop_visits = sum(1 for node, _ in bag.history if node in ("JA5", "JB5"))
        return loop_visits > 1

    def _is_excessive_transit(self, bag: BagInfo) -> bool:
        """Transit time > 2.5x estimated minimum."""
        if not bag.arrival_tick:
            return False
        transit = bag.arrival_tick - bag.release_tick
        min_est = self._estimate_shortest_path(bag.intake_node, bag.destination_gate)
        return transit > min_est * 2.5 and transit > 50

    def _is_unusual_route(self, bag: BagInfo) -> bool:
        """Excessive hops or backtracking."""
        if not bag.arrival_tick:
            return False
        nodes = [n for n, _ in bag.history]
        # Backtracking
        for i in range(len(nodes) - 1):
            if nodes[i] == nodes[i + 1]:
                return True
        # Excessive hops
        min_hops = self._estimate_shortest_path(bag.intake_node, bag.destination_gate)
        if len(nodes) > min_hops * 2:
            return True
        return False

    def _is_wrong_direction(self, bag: BagInfo) -> bool:
        """Returned to intake after leaving."""
        if not bag.arrival_tick or len(bag.history) < 3:
            return False
        nodes = [n for n, _ in bag.history]
        left_intake = False
        for node in nodes:
            if node.startswith("I"):
                if left_intake:
                    return True
            elif node.startswith("J") or node.startswith("S"):
                left_intake = True
        return False

    def _is_missed_deadline(self, bag: BagInfo) -> bool:
        """Bag has deadline and missed it."""
        if bag.deadline_tick and bag.arrival_tick:
            return bag.arrival_tick > bag.deadline_tick
        return False

    def _flag_suspicious(self, bag: BagInfo, reasons: List[str], tick: int):
        bag.is_suspicious = True
        bag.suspicious_reasons.extend(reasons)
        self.suspicious_bags.add(bag.bag_id)

    def _estimate_shortest_path(self, start: str, end: str) -> int:
        queue = [(start, 0)]
        visited = {start}
        while queue:
            node, dist = queue.pop(0)
            if node == end:
                return dist
            for neighbor in self.adjacency[node]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, dist + 1))
        return 20

    def _get_zone(self, node: str) -> str:
        ntype = self.node_types.get(node, "unknown")
        zones = {"intake": "INTAKE_ZONE", "junction": "JUNCTION_ZONE",
                 "spine": "SPINE_ZONE", "gate": "GATE_ZONE"}
        return zones.get(ntype, "UNKNOWN_ZONE")

    # =========================================================================
    # PER-TICK DETECTION RULES
    # =========================================================================

    def _is_cross_terminal_anomaly_at_tick(self, bag: BagInfo, history: List[Tuple[str, int]], arrival_tick: Optional[int]) -> bool:
        """Detect cross-terminal bag not using JA1<->JB1 bridge. Only evaluate on delivered bags."""
        if not arrival_tick:
            return False
        intake_term = "A" if bag.intake_node.startswith("I") else "B"
        gate_term = "A" if bag.destination_gate.startswith("GA") else "B"
        if intake_term != gate_term:
            for node, _ in history:
                if node in ("JA1", "JB1"):
                    return False
            return True
        return False

    def _is_stalled_at_tick(self, bag: BagInfo, history: List[Tuple[str, int]], current_node: Optional[str],
                            current_edge: Optional[str], arrival_tick: Optional[int], tick: int, edge_states: dict) -> bool:
        """Detect bags stuck on same node for too long."""
        if arrival_tick is not None or bag.release_tick > tick:
            return False
        if len(history) < 2:
            return False
        # Check if stuck at same node for > 30 ticks
        if not current_node:
            return False
        stuck_ticks = 0
        for node, h_tick in reversed(history):
            if node == current_node:
                stuck_ticks = tick - h_tick
            else:
                break
        return stuck_ticks > 30

    def _is_looping_at_tick(self, history: List[Tuple[str, int]], arrival_tick: Optional[int]) -> bool:
        """Detect multiple visits to loop trap nodes."""
        if not arrival_tick:
            return False
        loop_visits = sum(1 for node, _ in history if node in ("JA5", "JB5"))
        return loop_visits > 1

    def _is_excessive_transit_at_tick(self, bag: BagInfo, arrival_tick: Optional[int], tick: int) -> bool:
        """Transit time > 2.5x estimated minimum. Only evaluate on delivered bags."""
        if not arrival_tick:
            return False
        transit = arrival_tick - bag.release_tick
        min_est = self._estimate_shortest_path(bag.intake_node, bag.destination_gate)
        return transit > min_est * 2.5 and transit > 50

    def _is_unusual_route_at_tick(self, history: List[Tuple[str, int]], arrival_tick: Optional[int]) -> bool:
        """Excessive hops or backtracking."""
        if not arrival_tick:
            return False
        nodes = [n for n, _ in history]
        # Backtracking
        for i in range(len(nodes) - 1):
            if nodes[i] == nodes[i + 1]:
                return True
        # Excessive hops
        min_hops = self._estimate_shortest_path(history[0][0] if history else "IA1", nodes[-1] if nodes else "GA1")
        if len(nodes) > min_hops * 2:
            return True
        return False

    def _is_wrong_direction_at_tick(self, history: List[Tuple[str, int]], arrival_tick: Optional[int]) -> bool:
        """Returned to intake after leaving."""
        if not arrival_tick or len(history) < 3:
            return False
        nodes = [n for n, _ in history]
        left_intake = False
        for node in nodes:
            if node.startswith("I"):
                if left_intake:
                    return True
            elif node.startswith("J") or node.startswith("S"):
                left_intake = True
        return False

    def _is_missed_deadline_at_tick(self, bag: BagInfo, arrival_tick: Optional[int], tick: int) -> bool:
        """Bag has deadline and missed it."""
        if bag.deadline_tick and arrival_tick:
            return arrival_tick > bag.deadline_tick
        # Also flag if past deadline but not yet delivered
        if bag.deadline_tick and tick > bag.deadline_tick and arrival_tick is None:
            return True
        return False

    def get_bag_state_at_tick(self, bag_id: str, tick: int):
        """Get (current_node, current_edge, arrival_tick) for a bag at a specific tick."""
        if tick in self.bag_states_per_tick and bag_id in self.bag_states_per_tick[tick]:
            return self.bag_states_per_tick[tick][bag_id]
        # Bag not yet released at this tick
        bag = self.bags.get(bag_id)
        if bag and bag.release_tick > tick:
            return (None, None, None)
        # Fallback to final state (for bags already released)
        if bag:
            return (bag.current_node, bag.current_edge, bag.arrival_tick)
        return (None, None, None)

    def get_bag_history_at_tick(self, bag_id: str, tick: int) -> List[Tuple[str, int]]:
        """Get bag history up to a specific tick."""
        if tick in self.bag_history_per_tick and bag_id in self.bag_history_per_tick[tick]:
            return self.bag_history_per_tick[tick][bag_id]
        # Fallback to final history
        bag = self.bags.get(bag_id)
        if bag:
            return bag.history
        return []

# =============================================================================
# FOREIGN OBJECT DETECTOR
# =============================================================================

class ForeignObjectDetector:
    """Simulates and tracks foreign object incidents on conveyor tracks."""

    OBJECT_TYPES = ["DEBRIS", "SPILLAGE", "OBSTRUCTION", "UNKNOWN"]
    SEVERITIES = ["WARNING", "CRITICAL", "EMERGENCY"]

    # Predefined incident scenarios tied to specific tracks and phases
    INCIDENT_SCENARIOS = [
        # (track_id, start_tick, duration, severity, object_type, description)
        ("e_JA3_S3", 1850, 45, "WARNING", "DEBRIS", "Debris detected on Terminal A spine feed"),
        ("e_S2_S3_FWD", 2200, 120, "CRITICAL", "SPILLAGE", "Fluid spillage on main spine trunk — traction compromised"),
        ("e_JB2_S4", 2600, 80, "WARNING", "OBSTRUCTION", "Foreign object on Terminal B junction exit"),
        ("e_S4_S5", 3180, 180, "EMERGENCY", "OBSTRUCTION", "Large obstruction on spine trunk — track shutdown required"),
        ("e_JA1_JA2", 800, 30, "WARNING", "DEBRIS", "Minor debris on Terminal A junction internal"),
        ("e_S1_S6_FWD", 1550, 60, "CRITICAL", "SPILLAGE", "Oil spillage on detour belt — slip hazard"),
        ("e_JB5_S4", 3300, 40, "WARNING", "UNKNOWN", "Unidentified object on Terminal B loop exit"),
        ("e_S3_GA3", 1200, 25, "WARNING", "DEBRIS", "Packaging debris on Gate A3 feed"),
        ("e_S5_GB3", 2800, 90, "CRITICAL", "OBSTRUCTION", "Mechanical part fallen on Gate B3 feed"),
    ]

    def __init__(self):
        self.events: List[ForeignObjectEvent] = []
        self.active_events: Dict[str, ForeignObjectEvent] = {}
        self._initialize_events()

    def _initialize_events(self):
        for i, (track, start, duration, sev, obj_type, desc) in enumerate(self.INCIDENT_SCENARIOS):
            event = ForeignObjectEvent(
                event_id=f"FOE-{i+1:03d}",
                track_id=track,
                zone=self._get_zone_for_track(track),
                start_tick=start,
                end_tick=start + duration,
                severity=sev,
                description=desc,
                object_type=obj_type,
                status="DETECTED"
            )
            self.events.append(event)

    def _get_zone_for_track(self, track_id: str) -> str:
        base = track_id.replace("_FWD", "").replace("_REV", "")
        parts = base.split("_")
        if len(parts) >= 3:
            from_node = parts[1]
            ntype = NODE_TYPES.get(from_node, "unknown")
            if ntype == "intake":
                return "INTAKE_ZONE"
            elif ntype == "junction":
                return "JUNCTION_ZONE"
            elif ntype == "spine":
                return "SPINE_ZONE"
            elif ntype == "gate":
                return "GATE_ZONE"
        return "UNKNOWN_ZONE"

    def process_tick(self, tick: int) -> List[AlertEvent]:
        """Process a tick and return new alert events for foreign objects."""
        alerts = []

        for event in self.events:
            if event.start_tick == tick:
                event.status = "ONGOING"
                self.active_events[event.event_id] = event
                alerts.append(AlertEvent(
                    tick=tick,
                    track_id=event.track_id,
                    zone=event.zone,
                    description=f"Foreign object detected: {event.object_type} — {event.description}",
                    severity=event.severity,
                    status="ACTIVE",
                    event_type="FOREIGN_OBJECT"
                ))
            elif event.end_tick == tick and event.event_id in self.active_events:
                event.status = "CLEARED"
                del self.active_events[event.event_id]
                alerts.append(AlertEvent(
                    tick=tick,
                    track_id=event.track_id,
                    zone=event.zone,
                    description=f"Foreign object cleared: {event.object_type} — Track restored",
                    severity="INFO",
                    status="RESOLVED",
                    event_type="FOREIGN_OBJECT"
                ))
            elif event.event_id in self.active_events:
                event.status = "ONGOING"

        return alerts

    def get_active_events(self) -> List[ForeignObjectEvent]:
        return list(self.active_events.values())

    def get_event_for_track(self, track_id: str) -> Optional[ForeignObjectEvent]:
        base = track_id.replace("_FWD", "").replace("_REV", "")
        for event in self.active_events.values():
            if event.track_id == base or event.track_id == track_id:
                return event
        return None

# =============================================================================
# MAIN DASHBOARD APPLICATION
# =============================================================================

class BSDDashboard:
    def __init__(self, root, telemetry_path="live_telemetry.csv"):
        self.root = root
        self.root.title("Airport Innovation Challenge - BaggageIQ: Smart Baggage Handling Dashboard")
        self.root.geometry("1600x960")
        self.root.configure(bg=Colors.BG_DEEP)
        self.root.minsize(1400, 800)

        self.telemetry_path = telemetry_path
        self.current_tick = 1
        self.sub_tick = 0
        self.max_ticks = 3600
        self.is_playing = False
        self.playback_speed = 1.0
        self.updating_via_slider = False
        self.history: Dict[int, Dict[str, dict]] = {}

        # Selection state
        self.selected_track: Optional[str] = None
        self.selected_node: Optional[str] = None
        self.selected_bag: Optional[str] = None

        # Detection systems
        self.suspicious_detector: Optional[SuspiciousBagDetector] = None
        self.foreign_detector: Optional[ForeignObjectDetector] = None
        self.all_alerts: List[AlertEvent] = []
        self.seen_alert_keys: Set[Tuple] = set()  # Track unique alerts for running history

        # Telemetry-derived data
        self.bag_states: Dict[str, BagInfo] = {}
        self.track_stats: Dict[str, dict] = defaultdict(lambda: {
            "total_bags": 0, "max_occupancy": 0, "jam_count": 0, "wear": 0
        })

        # Simulation state
        self.simulation_running = False
        # If telemetry_path provided, use it for initial load
        tp = str(telemetry_path) if telemetry_path else None
        self.current_telemetry_path = tp if tp and os.path.exists(tp) else None
        bag_telemetry_path = tp.replace("live_telemetry", "live_bag_telemetry") if tp else None
        self.current_bag_telemetry_path = bag_telemetry_path if bag_telemetry_path and os.path.exists(bag_telemetry_path) else None
        self.last_simulation_summary = None  # Store actual evaluator results
        self.bag_history = {}  # tick -> {bag_id: position_data}

        # Load data (scenario + layout)
        self._load_scenario_and_layout()
        # Load telemetry if available
        self._load_telemetry_data()
        self.max_ticks = self.scenario_data["simulation"]["total_ticks"]
        self._compute_track_stats()
        self._reconstruct_bag_states()
        self._initialize_detectors()
        self._build_ui_layout()
        self._draw_static_network()
        self._update_display()

        # Bind keys
        self.root.bind("<space>", lambda e: self._toggle_playback())
        self.root.bind("<Left>", lambda e: self._prev_tick())
        self.root.bind("<Right>", lambda e: self._next_tick())
        self.root.bind("<Up>", lambda e: self._speed_up())
        self.root.bind("<Down>", lambda e: self._slow_down())

    def _load_scenario_and_layout(self):
        with open(BASE_DIR / "data" / "simulation_scenario.json", 'r') as f:
            self.scenario_data = json.load(f)
        with open(BASE_DIR / "data" / "network_layout.json", 'r') as f:
            self.layout_data = json.load(f)

        self.max_ticks = self.scenario_data["simulation"]["total_ticks"]

    def _load_telemetry_data(self):
        """Load telemetry from the current simulation run (set via current_telemetry_path)."""
        # Only load from the explicit current_telemetry_path set after a simulation run
        if not self.current_telemetry_path or not os.path.exists(self.current_telemetry_path):
            print("No telemetry data available for current run. Click RUN SIMULATION to generate.")
            # Initialize empty history for UI to work
            self.history = {}
            self.bag_history = {}
            self.max_ticks = self.scenario_data["simulation"]["total_ticks"]
            self._compute_track_stats()
            self._reconstruct_bag_states()
            return

        path = self.current_telemetry_path
        print(f"Parsing simulation telemetry dataset from {path}...")
        with open(path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                t = int(row["tick"])
                edge_id = row["edge_id"]

                if t not in self.history:
                    self.history[t] = {}

                self.history[t][edge_id] = {
                    "status": row["status"],
                    "fault_reason": row["fault_reason"],
                    "active_bags": int(row["active_bags"]),
                    "volume": int(row["cumulative_volume"])
                }
                self.max_ticks = max(self.max_ticks, t)

        print(f"Loaded {len(self.history)} ticks of telemetry data.")

        # Load per-bag telemetry for real-time KPIs
        self._load_bag_telemetry()

        # Compute track statistics
        self._compute_track_stats()
        # Reconstruct bag states from scenario
        self._reconstruct_bag_states()

    def _load_bag_telemetry(self):
        """Load per-bag position telemetry for real-time KPI computation."""
        self.bag_history = {}  # tick -> {bag_id: {position_data}}
        self.bag_arrival_ticks = {}  # bag_id -> arrival_tick (for cumulative KPIs)
        self.bag_release_ticks = {}  # bag_id -> release_tick
        self.bag_deadline_ticks = {}  # bag_id -> deadline_tick

        if not self.current_bag_telemetry_path or not os.path.exists(self.current_bag_telemetry_path):
            print("No bag telemetry available for current run.")
            return

        path = self.current_bag_telemetry_path
        print(f"Parsing bag telemetry dataset from {path}...")
        with open(path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                t = int(row["tick"])
                bag_id = row["bag_id"]

                if t not in self.bag_history:
                    self.bag_history[t] = {}

                arrival_tick = int(row["arrival_tick"]) if row["arrival_tick"] else None
                release_tick = int(row["release_tick"])
                deadline_tick = int(row["deadline_tick"]) if row["deadline_tick"] else None

                self.bag_history[t][bag_id] = {
                    "current_edge": row["current_edge"] or None,
                    "current_node": row["current_node"] or None,
                    "ticks_remaining": int(row["ticks_remaining"]) if row["ticks_remaining"] else 0,
                    "arrival_tick": arrival_tick,
                    "destination_gate": row["destination_gate"],
                    "release_tick": release_tick,
                    "deadline_tick": deadline_tick,
                    "diverted": row.get("diverted", "False").lower() == "true",
                    "diversion_tick": int(row["diversion_tick"]) if row.get("diversion_tick") else None
                }

                # Track bag metadata for cumulative KPIs
                if arrival_tick is not None:
                    self.bag_arrival_ticks[bag_id] = arrival_tick
                self.bag_release_ticks[bag_id] = release_tick
                if deadline_tick is not None:
                    self.bag_deadline_ticks[bag_id] = deadline_tick

        print(f"Loaded {len(self.bag_history)} ticks of bag telemetry data.")
        print(f"Tracked {len(self.bag_arrival_ticks)} bag deliveries.")

    def _compute_track_stats(self):
        for tick_data in self.history.values():
            for edge_id, data in tick_data.items():
                base = edge_id.replace("_FWD", "").replace("_REV", "")
                self.track_stats[base]["total_bags"] += data["active_bags"]
                self.track_stats[base]["max_occupancy"] = max(
                    self.track_stats[base]["max_occupancy"], data["active_bags"]
                )
                if data["status"] == "JAMMED":
                    self.track_stats[base]["jam_count"] += 1
                self.track_stats[base]["wear"] = data["volume"]

    def _reconstruct_bag_states(self):
        """Reconstruct bag histories from scenario and telemetry."""
        for bag_data in self.scenario_data.get("bags", []):
            bag = BagInfo(
                bag_id=bag_data["bag_id"],
                intake_node=bag_data["intake_node"],
                destination_gate=bag_data["destination_gate"],
                release_tick=bag_data["release_tick"],
                deadline_tick=bag_data.get("deadline_tick")
            )
            self.bag_states[bag.bag_id] = bag

        # We can't fully reconstruct without evaluator state, but we have scenario data

    def _initialize_detectors(self):
        self.suspicious_detector = SuspiciousBagDetector(self.scenario_data, self.layout_data, self.history)
        self.foreign_detector = ForeignObjectDetector()

    # =========================================================================
    # UI CONSTRUCTION
    # =========================================================================

    def _build_ui_layout(self):
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Dark.TFrame', background=Colors.BG_PANEL)
        style.configure('Dark.TLabel', background=Colors.BG_PANEL, foreground=Colors.FG_PRIMARY)
        style.configure('Dark.TLabelframe', background=Colors.BG_PANEL, foreground=Colors.FG_PRIMARY)
        style.configure('Dark.TLabelframe.Label', background=Colors.BG_PANEL, foreground=Colors.ACCENT_CYAN, font=("Segoe UI", 9, "bold"))
        style.configure('KPI.TLabel', background=Colors.BG_CARD, foreground=Colors.FG_PRIMARY, font=("Consolas", 14, "bold"))
        style.configure('KPISub.TLabel', background=Colors.BG_CARD, foreground=Colors.FG_SECONDARY, font=("Segoe UI", 10))

        # Main container
        main_container = tk.Frame(self.root, bg=Colors.BG_DEEP)
        main_container.pack(fill=tk.BOTH, expand=True)

        # ========== HEADER ==========
        header = tk.Frame(main_container, bg=Colors.BG_PANEL, height=100)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        # ========== PLAYBACK CONTROLS (BOTTOM) ==========
        # Must be packed BEFORE content so content fills space between header and controls
        controls = tk.Frame(main_container, bg=Colors.BG_PANEL, height=96)
        controls.pack(fill=tk.X, side=tk.BOTTOM, padx=8, pady=8)
        controls.pack_propagate(False)

        self._create_playback_controls(controls)

        # Top row: Title + Phase
        top_row = tk.Frame(header, bg=Colors.BG_PANEL)
        top_row.pack(fill=tk.X, side=tk.TOP, padx=16, pady=(8, 4))

        title_frame = tk.Frame(top_row, bg=Colors.BG_PANEL)
        title_frame.pack(side=tk.LEFT)

        tk.Label(title_frame, text="BaggageIQ: Smart Baggage Handling Dashboard", font=("Segoe UI", 14, "bold"),
                 fg=Colors.ACCENT_CYAN, bg=Colors.BG_PANEL).pack(anchor=tk.W)
        tk.Label(title_frame, text="Baggage Handling System — Control Room Display",
                 font=("Segoe UI", 8), fg=Colors.FG_SECONDARY, bg=Colors.BG_PANEL).pack(anchor=tk.W)

        # Phase indicator in header
        self.phase_frame = tk.Frame(top_row, bg=Colors.BG_PANEL)
        self.phase_frame.pack(side=tk.RIGHT)
        self.lbl_phase = tk.Label(self.phase_frame, text="PHASE: WARM-UP", font=("Consolas", 13, "bold"),
                                   fg=Colors.ACCENT_BLUE, bg=Colors.BG_PANEL)
        self.lbl_phase.pack(side=tk.RIGHT, padx=16, pady=8)

        # Bottom row: Scenario & Solution selectors + Run button
        control_row = tk.Frame(header, bg=Colors.BG_PANEL)
        control_row.pack(fill=tk.X, side=tk.BOTTOM, padx=16, pady=(0, 8))

        # Scenario selector
        scenario_frame = tk.Frame(control_row, bg=Colors.BG_PANEL)
        scenario_frame.pack(side=tk.LEFT, padx=(0, 12))
        tk.Label(scenario_frame, text="SCENARIO:", font=("Segoe UI", 8, "bold"),
                 fg=Colors.FG_SECONDARY, bg=Colors.BG_PANEL).pack(side=tk.LEFT, padx=(0, 4))
        self.scenario_var = tk.StringVar(value="baseline")
        scenario_combo = ttk.Combobox(scenario_frame, textvariable=self.scenario_var,
                                       values=list(SCENARIOS.keys()), state="readonly", width=20, font=("Segoe UI", 8))
        scenario_combo.pack(side=tk.LEFT)
        self.scenario_combo = scenario_combo

        # Solution selector
        solution_frame = tk.Frame(control_row, bg=Colors.BG_PANEL)
        solution_frame.pack(side=tk.LEFT, padx=(0, 12))
        tk.Label(solution_frame, text="SOLUTION:", font=("Segoe UI", 8, "bold"),
                 fg=Colors.FG_SECONDARY, bg=Colors.BG_PANEL).pack(side=tk.LEFT, padx=(0, 4))
        self.solution_var = tk.StringVar(value="optimized")
        solution_combo = ttk.Combobox(solution_frame, textvariable=self.solution_var,
                                       values=["baseline", "optimized"], state="readonly", width=14, font=("Segoe UI", 8))
        solution_combo.pack(side=tk.LEFT)
        self.solution_combo = solution_combo

        # Run button
        self.btn_run = tk.Button(control_row, text="▶ RUN SIMULATION", width=18, bg=Colors.ACCENT_GREEN, fg="white",
                                  font=("Segoe UI", 9, "bold"), relief=tk.FLAT, command=self._run_simulation)
        self.btn_run.pack(side=tk.LEFT, padx=(12, 0))

        # Run status label
        self.lbl_run_status = tk.Label(control_row, text="Ready", font=("Segoe UI", 8),
                                        fg=Colors.FG_SECONDARY, bg=Colors.BG_PANEL)
        self.lbl_run_status.pack(side=tk.LEFT, padx=12)

        # ========== MAIN CONTENT AREA (3 columns) ==========
        content = tk.Frame(main_container, bg=Colors.BG_DEEP)
        content.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Column weights: Network (60%), KPI+Inspector (25%), Alerts (15%)
        content.grid_columnconfigure(0, weight=6, minsize=700)
        content.grid_columnconfigure(1, weight=3, minsize=300)
        content.grid_columnconfigure(2, weight=1, minsize=240)  
        content.grid_rowconfigure(0, weight=1)

        # ---- LEFT: NETWORK VISUALIZATION ----
        net_frame = tk.Frame(content, bg=Colors.BG_PANEL, bd=1, relief=tk.SOLID, highlightbackground="#2a2a35")
        net_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        net_header = tk.Frame(net_frame, bg=Colors.BG_CARD, height=36)
        net_header.pack(fill=tk.X)
        net_header.pack_propagate(False)
        tk.Label(net_header, text="NETWORK TOPOLOGY", font=("Segoe UI", 9, "bold"),
                 fg=Colors.ACCENT_CYAN, bg=Colors.BG_CARD).pack(side=tk.LEFT, padx=12, pady=8)

        # Legend
        legend_frame = tk.Frame(net_header, bg=Colors.BG_CARD)
        legend_frame.pack(side=tk.RIGHT, padx=12)
        self._create_network_legend(legend_frame)

        # Canvas - scaled to fit network in view
        canvas_frame = tk.Frame(net_frame, bg=Colors.BG_CANVAS)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.canvas = tk.Canvas(canvas_frame, bg=Colors.BG_CANVAS, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Scaling factors for fit-to-view (computed in _compute_scale)
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0

        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Motion>", self._on_canvas_hover)
        self.canvas.bind("<Leave>", self._on_canvas_leave)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        # ---- CENTER: KPI PANEL + INSPECTOR ----
        center_frame = tk.Frame(content, bg=Colors.BG_DEEP)
        center_frame.grid(row=0, column=1, sticky="nsew", padx=4)
        center_frame.grid_rowconfigure(0, weight=3)  # KPI
        center_frame.grid_rowconfigure(1, weight=2)  # Inspector

        # KPI Panel
        kpi_frame = tk.Frame(center_frame, bg=Colors.BG_PANEL, bd=1, relief=tk.SOLID, highlightbackground="#2a2a35")
        kpi_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 4))

        tk.Label(kpi_frame, text="KEY PERFORMANCE INDICATORS", font=("Segoe UI", 9, "bold"),
                 fg=Colors.ACCENT_CYAN, bg=Colors.BG_PANEL).pack(anchor=tk.W, padx=12, pady=8)

        self.kpi_container = tk.Frame(kpi_frame, bg=Colors.BG_PANEL)
        self.kpi_container.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
        self._create_kpi_cards()

        # Inspector Panel
        inspect_frame = tk.Frame(center_frame, bg=Colors.BG_PANEL, bd=1, relief=tk.SOLID, highlightbackground="#2a2a35")
        inspect_frame.grid(row=1, column=0, sticky="nsew", pady=(4, 0))

        inspect_header = tk.Frame(inspect_frame, bg=Colors.BG_CARD, height=36)
        inspect_header.pack(fill=tk.X)
        inspect_header.pack_propagate(False)
        tk.Label(inspect_header, text="TRACK / BAG INSPECTOR", font=("Segoe UI", 9, "bold"),
                 fg=Colors.ACCENT_CYAN, bg=Colors.BG_CARD).pack(side=tk.LEFT, padx=12, pady=8)
        self.inspect_title = tk.Label(inspect_header, text="Select a track, node, or bag",
                                       font=("Segoe UI", 8), fg=Colors.FG_SECONDARY, bg=Colors.BG_CARD)
        self.inspect_title.pack(side=tk.LEFT, padx=8, pady=8)

        # Scrollable inspector content
        inspect_canvas = tk.Canvas(inspect_frame, bg=Colors.BG_PANEL, highlightthickness=0)
        inspect_scrollbar = ttk.Scrollbar(inspect_frame, orient="vertical", command=inspect_canvas.yview)
        self.inspect_content = tk.Frame(inspect_canvas, bg=Colors.BG_PANEL)

        self.inspect_content.bind(
            "<Configure>",
            lambda e: inspect_canvas.configure(scrollregion=inspect_canvas.bbox("all"))
        )

        inspect_canvas.create_window((0, 0), window=self.inspect_content, anchor="nw", tags="content")
        inspect_canvas.configure(yscrollcommand=inspect_scrollbar.set)

        def _resize_canvas(event):
            inspect_canvas.itemconfig("content", width=event.width)
        inspect_canvas.bind("<Configure>", _resize_canvas)

        inspect_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)
        inspect_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=8, padx=(0, 8))

        self._create_inspector_placeholder()

        # Store canvas for mousewheel binding
        self.inspect_canvas = inspect_canvas

        def _on_mousewheel(event):
            inspect_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        inspect_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # ---- RIGHT: ALERT LOG ----
        alert_frame = tk.Frame(content, bg=Colors.BG_PANEL, bd=1, relief=tk.SOLID, highlightbackground="#2a2a35")
        alert_frame.grid(row=0, column=2, sticky="nsew", padx=(4, 0))

        alert_header = tk.Frame(alert_frame, bg=Colors.BG_CARD, height=36)
        alert_header.pack(fill=tk.X)
        alert_header.pack_propagate(False)
        tk.Label(alert_header, text="ALERT / EVENT LOG", font=("Segoe UI", 9, "bold"),
                 fg=Colors.ACCENT_CYAN, bg=Colors.BG_CARD).pack(side=tk.LEFT, padx=12, pady=8)
        self.lbl_alert_count = tk.Label(alert_header, text="0 ACTIVE", font=("Consolas", 9, "bold"),
                                         fg=Colors.ACCENT_ORANGE, bg=Colors.BG_CARD)
        self.lbl_alert_count.pack(side=tk.RIGHT, padx=12, pady=8)

        # Filter toolbar
        filter_frame = tk.Frame(alert_frame, bg=Colors.BG_PANEL)
        filter_frame.pack(fill=tk.X, padx=8, pady=4)

        self.alert_filter = tk.StringVar(value="ALL")
        for f in ["ALL", "CRITICAL", "WARNING", "INFO", "SUSPICIOUS", "FOREIGN", "DIVERSION"]:
            rb = tk.Radiobutton(filter_frame, text=f, variable=self.alert_filter, value=f,
                                bg=Colors.BG_PANEL, fg=Colors.FG_PRIMARY, selectcolor=Colors.BG_CARD,
                                activebackground=Colors.BG_PANEL, activeforeground=Colors.ACCENT_CYAN,
                                font=("Segoe UI", 7), indicatoron=0, width=8,
                                command=self._refresh_alert_list)
            rb.pack(side=tk.LEFT, padx=1)

        # Alert list with scrollbar
        list_frame = tk.Frame(alert_frame, bg=Colors.BG_PANEL)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self.alert_tree = ttk.Treeview(list_frame, columns=("tick", "severity", "track", "desc"),
                                        show="headings", height=25)
        self.alert_tree.heading("tick", text="TICK")
        self.alert_tree.heading("severity", text="SEV")
        self.alert_tree.heading("track", text="TRACK/ZONE")
        self.alert_tree.heading("desc", text="DESCRIPTION")
        self.alert_tree.column("tick", width=50, anchor=tk.CENTER)
        self.alert_tree.column("severity", width=55, anchor=tk.CENTER)
        self.alert_tree.column("track", width=90, anchor=tk.W)
        self.alert_tree.column("desc", width=180, anchor=tk.W)

        # Style treeview
        style.configure("Treeview", background=Colors.BG_CARD, foreground=Colors.FG_PRIMARY,
                        fieldbackground=Colors.BG_CARD, borderwidth=0, font=("Consolas", 8))
        style.configure("Treeview.Heading", background=Colors.BG_CARD, foreground=Colors.ACCENT_CYAN,
                        font=("Segoe UI", 8, "bold"), borderwidth=1)
        style.map("Treeview", background=[("selected", Colors.ACCENT_BLUE)])

        self.alert_tree.tag_configure("CRITICAL", foreground=Colors.ACCENT_RED)
        self.alert_tree.tag_configure("EMERGENCY", foreground=Colors.ACCENT_RED)
        self.alert_tree.tag_configure("WARNING", foreground=Colors.ACCENT_ORANGE)
        self.alert_tree.tag_configure("INFO", foreground=Colors.ACCENT_BLUE)
        self.alert_tree.tag_configure("SUSPICIOUS", foreground=Colors.ACCENT_PURPLE)
        self.alert_tree.tag_configure("FOREIGN", foreground=Colors.ACCENT_AMBER)
        self.alert_tree.tag_configure("DIVERSION", foreground=Colors.ACCENT_AMBER)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.alert_tree.yview)
        self.alert_tree.configure(yscrollcommand=scrollbar.set)
        self.alert_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.alert_tree.bind("<<TreeviewSelect>>", self._on_alert_select)

    def _create_network_legend(self, parent):
        legend_items = [
            ("IDLE", Colors.IDLE),
            ("LOW", Colors.OCCUPIED_LOW),
            ("MED", Colors.OCCUPIED_MED),
            ("HIGH", Colors.OCCUPIED_HIGH),
            ("CONGESTED", Colors.CONGESTED),
            ("JAMMED", Colors.JAMMED),
            ("DISABLED", Colors.DISABLED),
            ("SUSPICIOUS", Colors.SUSPICIOUS),
            ("FOREIGN OBJ", Colors.FOREIGN_OBJECT),
        ]
        for label, color in legend_items:
            item = tk.Frame(parent, bg=Colors.BG_CARD)
            item.pack(side=tk.LEFT, padx=4)
            tk.Canvas(item, width=14, height=14, bg=color, highlightthickness=0).pack(side=tk.LEFT)
            tk.Label(item, text=label, font=("Segoe UI", 8), fg=Colors.FG_SECONDARY, bg=Colors.BG_CARD).pack(side=tk.LEFT, padx=2)

    def _create_kpi_cards(self):
        self.kpi_cards = {}

        kpi_defs = [
            ("misrouted", "MISROUTED BAGS", "0", Colors.ACCENT_RED, "Bags missing deadline or stranded"),
            ("mean_latency", "MEAN DELIVERY LATENCY", "0.0 ticks", Colors.ACCENT_BLUE, "Avg transit time (delivered)"),
            ("in_transit", "BAGS IN TRANSIT", "0", Colors.ACCENT_ORANGE, "Currently on conveyor network"),
            ("delivered", "SUCCESSFULLY DELIVERED", "0", Colors.ACCENT_GREEN, "Arrived at destination gate"),
            ("diverted", "DIVERTED BAGS", "0", Colors.ACCENT_AMBER, "Rerouted to inspection area"),
            ("suspicious", "SUSPICIOUS BAGS", "0", Colors.ACCENT_PURPLE, "Flagged by detection system"),
            ("foreign_objects", "FOREIGN OBJECTS", "0", Colors.ACCENT_AMBER, "Active foreign-object incidents"),
        ]

        for i, (key, label, value, color, desc) in enumerate(kpi_defs):
            row = i // 2
            col = i % 2

            card = tk.Frame(self.kpi_container, bg=Colors.BG_CARD, bd=1, relief=tk.SOLID, highlightbackground="#2a2a35")
            card.grid(row=row, column=col, sticky="nsew", padx=3, pady=3)
            self.kpi_container.grid_columnconfigure(col, weight=1)

            # Color accent bar
            accent = tk.Frame(card, bg=color, width=4)
            accent.pack(fill=tk.Y, side=tk.LEFT)

            content = tk.Frame(card, bg=Colors.BG_CARD)
            content.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

            tk.Label(content, text=label, font=("Segoe UI", 7, "bold"),
                     fg=Colors.FG_MUTED, bg=Colors.BG_CARD).pack(anchor=tk.W)

            val_label = tk.Label(content, text=value, font=("Consolas", 16, "bold"),
                                  fg=color, bg=Colors.BG_CARD)
            val_label.pack(anchor=tk.W, pady=(2, 0))

            tk.Label(content, text=desc, font=("Segoe UI", 7),
                     fg=Colors.FG_MUTED, bg=Colors.BG_CARD).pack(anchor=tk.W)

            self.kpi_cards[key] = {"value": val_label, "color": color}

    def _create_inspector_placeholder(self):
        self.inspect_placeholder = tk.Label(self.inspect_content,
            text="▸ Click a track (line) to view occupancy, jam history, wear\n"
                 "▸ Click a node (circle) to view connections, throughput\n"
                 "▸ Click a suspicious bag badge to view route history\n"
                 "▸ Alert log selection shows related track/bag",
            font=("Segoe UI", 9), fg=Colors.FG_SECONDARY, bg=Colors.BG_PANEL, justify=tk.LEFT)
        self.inspect_placeholder.pack(fill=tk.BOTH, expand=True)

        self.inspect_detail_frame = tk.Frame(self.inspect_content, bg=Colors.BG_PANEL)

    def _create_playback_controls(self, parent):
        # Left: Playback buttons
        btn_frame = tk.Frame(parent, bg=Colors.BG_PANEL)
        btn_frame.pack(side=tk.LEFT, padx=16, pady=8)

        self.btn_play = tk.Button(btn_frame, text="▶ PLAY", width=10, bg=Colors.ACCENT_GREEN, fg="white",
                                  font=("Segoe UI", 9, "bold"), relief=tk.FLAT, command=self._toggle_playback)
        self.btn_play.pack(side=tk.LEFT, padx=3)

        for txt, cmd in [("⏮ STEP -", self._prev_tick), ("STEP + ⏭", self._next_tick),
                         ("⏪ JUMP PREV EVENT", self._jump_prev_event), ("JUMP NEXT EVENT ⏩", self._jump_next_event),
                         ("🔍 FIT VIEW", self._fit_to_view)]:
            tk.Button(btn_frame, text=txt, width=14, bg=Colors.BG_CARD, fg=Colors.FG_PRIMARY,
                      font=("Segoe UI", 8), relief=tk.FLAT, command=cmd).pack(side=tk.LEFT, padx=3)

        # Speed control
        speed_frame = tk.Frame(btn_frame, bg=Colors.BG_PANEL)
        speed_frame.pack(side=tk.LEFT, padx=10)
        tk.Label(speed_frame, text="SPEED:", font=("Segoe UI", 8), fg=Colors.FG_SECONDARY, bg=Colors.BG_PANEL).pack(side=tk.LEFT)
        self.speed_var = tk.DoubleVar(value=1.0)
        speed_scale = tk.Scale(speed_frame, from_=0.25, to=4.0, resolution=0.25, orient=tk.HORIZONTAL,
                               variable=self.speed_var, bg=Colors.BG_PANEL, fg=Colors.FG_PRIMARY,
                               highlightthickness=0, troughcolor=Colors.BG_CARD, length=120,
                               font=("Consolas", 8), command=self._on_speed_change)
        speed_scale.pack(side=tk.LEFT, padx=4)
        self.lbl_speed = tk.Label(speed_frame, text="1.0×", font=("Consolas", 9, "bold"),
                                   fg=Colors.ACCENT_CYAN, bg=Colors.BG_PANEL)
        self.lbl_speed.pack(side=tk.LEFT, padx=4)

        # Center: Timeline scrubber with phase markers
        timeline_frame = tk.Frame(parent, bg=Colors.BG_PANEL)
        timeline_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=20, pady=8)

        # Phase markers row
        phase_markers = tk.Frame(timeline_frame, bg=Colors.BG_PANEL, height=20)
        phase_markers.pack(fill=tk.X)
        for phase in PHASES:
            rel_start = phase["start"] / self.max_ticks
            rel_end = phase["end"] / self.max_ticks
            marker = tk.Frame(phase_markers, bg=phase["color"], height=4)
            marker.place(relx=rel_start, relwidth=rel_end - rel_start)
            lbl = tk.Label(phase_markers, text=phase["label"], font=("Segoe UI", 6, "bold"),
                           fg=phase["color"], bg=Colors.BG_PANEL)
            lbl.place(relx=rel_start + 0.005, rely=0.5, anchor=tk.W)

        # Scrubber
        self.slider = tk.Scale(timeline_frame, from_=1, to=self.max_ticks, orient=tk.HORIZONTAL,
                               bg=Colors.BG_PANEL, fg=Colors.FG_PRIMARY, highlightthickness=0,
                               troughcolor=Colors.BG_CARD, activebackground=Colors.ACCENT_CYAN,
                               font=("Consolas", 8), showvalue=0,
                               command=self._on_slider_scrub)
        self.slider.pack(fill=tk.X, pady=(4, 0))

        # Right: Tick counter and status
        status_frame = tk.Frame(parent, bg=Colors.BG_PANEL)
        status_frame.pack(side=tk.RIGHT, padx=16, pady=8)

        self.lbl_tick_counter = tk.Label(status_frame, text="TICK: 0001 / 3600",
                                         font=("Consolas", 14, "bold"), fg=Colors.ACCENT_CYAN, bg=Colors.BG_PANEL)
        self.lbl_tick_counter.pack(anchor=tk.E)

        self.lbl_playback_status = tk.Label(status_frame, text="PAUSED",
                                             font=("Segoe UI", 9), fg=Colors.FG_SECONDARY, bg=Colors.BG_PANEL)
        self.lbl_playback_status.pack(anchor=tk.E)

        # Active alerts summary
        self.lbl_active_summary = tk.Label(status_frame, text="ACTIVE: 0 JAMS | 0 SUSPICIOUS | 0 FOREIGN",
                                            font=("Consolas", 8), fg=Colors.FG_SECONDARY, bg=Colors.BG_PANEL)
        self.lbl_active_summary.pack(anchor=tk.E, pady=(4, 0))

    # =========================================================================
    # NETWORK RENDERING
    # =========================================================================

    def _draw_static_network(self):
        """Draw nodes and static edge lines (background topology)."""
        self.canvas.delete("static_topology")
        self.canvas.delete("static_node")

        if self.scale_factor <= 0:
            return

        # Scaled radius
        r = NODE_RADIUS * self.scale_factor

        # Draw edges first (behind nodes)
        for u, v in EDGE_CONNECTIONS:
            if u in NODE_COORDINATES and v in NODE_COORDINATES:
                x1, y1 = self._transform_coords(*NODE_COORDINATES[u])
                x2, y2 = self._transform_coords(*NODE_COORDINATES[v])
                # Draw faint topology line
                self.canvas.create_line(x1, y1, x2, y2, fill="#1a1a24", width=max(1, 1.5 * self.scale_factor), tags="static_topology")

        # Draw nodes
        for node_id, (x, y) in NODE_COORDINATES.items():
            ntype = NODE_TYPES.get(node_id, "unknown")
            color = NODE_TYPE_COLORS.get(ntype, Colors.JUNCTION)
            label_color = Colors.FG_PRIMARY

            tx, ty = self._transform_coords(x, y)
            # Node circle
            node_obj = self.canvas.create_oval(tx-r, ty-r, tx+r, ty+r, fill=color, outline="#3a3a45", width=max(1, 2 * self.scale_factor),
                                               tags=("static_node", f"node_{node_id}"))
            # Node label
            font_size = max(6, int(8 * self.scale_factor))
            self.canvas.create_text(tx, ty, text=node_id, font=("Consolas", font_size, "bold"), fill=label_color,
                                    tags=("static_node", f"node_{node_id}_label"))
            # Type indicator
            type_short = NODE_TYPE_LABELS.get(ntype, "?")[:3]
            self.canvas.create_text(tx, ty + r + max(8, 10 * self.scale_factor), text=type_short, font=("Segoe UI", max(5, int(6 * self.scale_factor)), "bold"),
                                    fill=Colors.FG_MUTED, tags=("static_node", f"node_{node_id}_type"))

    def _update_display(self):
        """Update dynamic overlay: edge states, bags, alerts, selection highlights."""
        self.canvas.delete("dynamic_overlay")

        tick_data = self.history.get(self.current_tick, {})
        active_jams = 0
        active_congested = 0
        progress = self.sub_tick / float(SUB_FRAMES_PER_TICK)

        # Process foreign object events for this tick (updates detector internal state)
        self.foreign_detector.process_tick(self.current_tick)

        # Process suspicious bag detection for this tick (uses precomputed alerts)
        if self.suspicious_detector:
            self.suspicious_detector.process_telemetry_tick(self.current_tick, tick_data)

        # Update bag states from telemetry (approximate)
        self._update_bag_approximations(tick_data)

        # Draw edges with dynamic state
        active_jams = 0
        active_congested = 0
        for u, v in EDGE_CONNECTIONS:
            jams, cong = self._draw_edge_state(u, v, tick_data, progress)
            active_jams += jams
            active_congested += cong
            # Also draw reverse if bidirectional
            if (u, v) in BIDIRECTIONAL_EDGES or (v, u) in BIDIRECTIONAL_EDGES:
                jams, cong = self._draw_edge_state(v, u, tick_data, progress, is_reverse=True)
                active_jams += jams
                active_congested += cong

        # Draw selection highlights
        if self.selected_track:
            self._highlight_track(self.selected_track)
        if self.selected_node:
            self._highlight_node(self.selected_node)

        # Draw suspicious bag indicators
        self._draw_suspicious_indicators()

        # Draw diverted bag indicators
        self._draw_diverted_indicators()

        # Draw foreign object indicators
        self._draw_foreign_object_indicators()

        # Update UI
        self._update_kpi_panel()
        self._update_alert_list()
        self._update_phase_indicator()
        self._update_playback_status()
        self._update_tick_counter()

        # Sync slider
        self.updating_via_slider = True
        self.slider.set(self.current_tick)
        self.updating_via_slider = False

    def _draw_edge_state(self, u: str, v: str, tick_data: dict, progress: float, is_reverse: bool = False):
        """Draw edge state and return (jam_count, congested_count)."""
        if u not in NODE_COORDINATES or v not in NODE_COORDINATES or self.scale_factor <= 0:
            return 0, 0

        x1, y1 = self._transform_coords(*NODE_COORDINATES[u])
        x2, y2 = self._transform_coords(*NODE_COORDINATES[v])

        dx, dy = x2 - x1, y2 - y1
        dist = math.hypot(dx, dy)
        if dist == 0:
            return 0, 0
        ux, uy = dx / dist, dy / dist
        nx, ny = -uy, ux

        # Determine edge ID
        base_id = f"e_{u}_{v}"
        edge_id_fwd = base_id + ("_REV" if is_reverse else "_FWD")
        edge_id_rev = base_id + ("_FWD" if is_reverse else "_REV")

        # Get telemetry for this direction (bidirectional edges use _FWD/_REV, unidirectional use base_id)
        data = tick_data.get(edge_id_fwd) or tick_data.get(edge_id_rev) or tick_data.get(base_id) or {}
        status = data.get("status", "OPERATIONAL")
        bags = data.get("active_bags", 0)
        fault = data.get("fault_reason", "NONE")

        # Check foreign object
        fo_event = self.foreign_detector.get_event_for_track(base_id)

        # Line offset for parallel tracks (scaled)
        line_offset = (-6 if is_reverse else 6) * self.scale_factor

        # Trim to node radius (scaled)
        trim = (NODE_RADIUS + 8) * self.scale_factor
        x1s = x1 + ux * trim + nx * line_offset
        y1s = y1 + uy * trim + ny * line_offset
        x2s = x2 - ux * trim + nx * line_offset
        y2s = y2 - uy * trim + ny * line_offset

        # Determine color and width (scaled)
        jam_count = 0
        cong_count = 0
        if fo_event and fo_event.status == "ONGOING":
            line_color = Colors.FOREIGN_OBJECT
            line_width = 4.0 * self.scale_factor
        elif status == "JAMMED":
            line_color = Colors.JAMMED
            line_width = 3.5 * self.scale_factor
            jam_count = 1
        elif bags > 10:
            line_color = Colors.CONGESTED
            line_width = 3.0 * self.scale_factor
            cong_count = 1
        elif bags > 5:
            line_color = Colors.OCCUPIED_HIGH
            line_width = 2.5 * self.scale_factor
        elif bags > 2:
            line_color = Colors.OCCUPIED_MED
            line_width = 2.0 * self.scale_factor
        elif bags > 0:
            line_color = Colors.OCCUPIED_LOW
            line_width = 1.5 * self.scale_factor
        else:
            line_color = Colors.IDLE
            line_width = 1.0 * self.scale_factor

        # Highlight if selected
        if self.selected_track == base_id or self.selected_track in (edge_id_fwd, edge_id_rev):
            line_width += 1.5 * self.scale_factor
            line_color = Colors.ACCENT_CYAN

        # Diversion track styling (dashed amber line) - ONLY when diversion is active (bags > 0)
        is_diversion = ("DIVERSION_INSPECTION" in (u, v))
        if is_diversion and bags > 0:
            line_color = Colors.DIVERSION
            line_width = 2.0 * self.scale_factor
            dash_pattern = (int(8 * self.scale_factor), int(4 * self.scale_factor))
        else:
            dash_pattern = None

        # Draw line with scaled arrow
        arrow_size = max(6, int(10 * self.scale_factor))
        line_kwargs = {"fill": line_color, "width": line_width, "arrow": tk.LAST,
                       "arrowshape": (arrow_size, arrow_size + 1, 4), "tags": "dynamic_overlay"}
        if dash_pattern:
            line_kwargs["dash"] = dash_pattern
        self.canvas.create_line(x1s, y1s, x2s, y2s, **line_kwargs)

        # Draw bags on edge
        if bags > 0:
            self._draw_bags_on_edge(x1s, y1s, x2s, y2s, bags, progress, status, line_color)

        # Draw occupancy label
        if bags > 0:
            mid_x = (x1s + x2s) / 2
            mid_y = (y1s + y2s) / 2
            font_size = max(5, int(7 * self.scale_factor))
            self.canvas.create_text(mid_x + nx * 12 * self.scale_factor, mid_y + ny * 12 * self.scale_factor,
                                    text=str(bags), font=("Consolas", font_size, "bold"),
                                    fill=Colors.FG_PRIMARY, tags="dynamic_overlay")

        return jam_count, cong_count

    def _draw_bags_on_edge(self, x1, y1, x2, y2, count, progress, status, color):
        bag_radius = max(2, int(3 * self.scale_factor))
        outline_width = max(0.5, 0.5 * self.scale_factor)

        if status == "JAMMED":
            # Static spaced bags
            for i in range(min(count, 8)):
                pos = 0.15 + (i * 0.1)
                if pos > 0.85: pos = 0.85
                px = x1 + pos * (x2 - x1)
                py = y1 + pos * (y2 - y1)
                self.canvas.create_oval(px-bag_radius, py-bag_radius, px+bag_radius, py+bag_radius,
                                        fill=Colors.JAMMED, outline="#fff", width=outline_width,
                                        tags="dynamic_overlay")
        else:
            # Moving bags
            for i in range(min(count, 6)):
                pos = progress - (i * 0.15)
                if 0.0 <= pos <= 1.0:
                    px = x1 + pos * (x2 - x1)
                    py = y1 + pos * (y2 - y1)
                    self.canvas.create_oval(px-bag_radius, py-bag_radius, px+bag_radius, py+bag_radius,
                                            fill=color, outline="#fff", width=outline_width,
                                            tags="dynamic_overlay")

    def _draw_suspicious_indicators(self):
        if not self.suspicious_detector or self.scale_factor <= 0:
            return

        for bag_id in self.suspicious_detector.suspicious_bags:
            node, edge, arrival = self.suspicious_detector.get_bag_state_at_tick(bag_id, self.current_tick)
            # Only show for bags currently in transit (not yet delivered)
            if node is None or arrival is not None:
                continue

            # Draw indicator at bag's current node
            if node in NODE_COORDINATES:
                tx, ty = self._transform_coords(*NODE_COORDINATES[node])
                r = (NODE_RADIUS + 18) * self.scale_factor
                # Pulsing ring
                pulse = abs(math.sin(self.current_tick * 0.2)) * 4 * self.scale_factor
                self.canvas.create_oval(tx-r-pulse, ty-r-pulse, tx+r+pulse, ty+r+pulse,
                                        outline=Colors.SUSPICIOUS, width=max(1, 2 * self.scale_factor), dash=(4, 4),
                                        tags="dynamic_overlay")
                # Badge
                font_size = max(5, int(7 * self.scale_factor))
                self.canvas.create_text(tx, ty - r - 10 * self.scale_factor, text="⚠ SUS", font=("Segoe UI", font_size, "bold"),
                                        fill=Colors.SUSPICIOUS, tags="dynamic_overlay")

    def _draw_diverted_indicators(self):
        """Draw indicators for bags that have been diverted to inspection."""
        if self.scale_factor <= 0:
            return

        # Check bag history for diverted bags
        available_ticks = [t for t in self.bag_history.keys() if t <= self.current_tick]
        if not available_ticks:
            return

        tick_to_use = max(available_ticks)
        tick_bags = self.bag_history[tick_to_use]

        for bag_id, bag_data in tick_bags.items():
            if bag_data.get("diverted", False):
                node = bag_data.get("current_node")
                if node and node in NODE_COORDINATES:
                    tx, ty = self._transform_coords(*NODE_COORDINATES[node])
                    r = (NODE_RADIUS + 18) * self.scale_factor
                    # Pulsing ring (amber)
                    pulse = abs(math.sin(self.current_tick * 0.2)) * 4 * self.scale_factor
                    self.canvas.create_oval(tx-r-pulse, ty-r-pulse, tx+r+pulse, ty+r+pulse,
                                            outline=Colors.DIVERSION, width=max(1, 2 * self.scale_factor), dash=(4, 4),
                                            tags="dynamic_overlay")
                    # Badge
                    font_size = max(5, int(7 * self.scale_factor))
                    self.canvas.create_text(tx, ty - r - 10 * self.scale_factor, text="🔍 DIV", font=("Segoe UI", font_size, "bold"),
                                            fill=Colors.DIVERSION, tags="dynamic_overlay")

    def _draw_foreign_object_indicators(self):
        if self.scale_factor <= 0:
            return
        # Check each event against current tick (not detector internal state)
        for event in self.foreign_detector.events:
            if event.start_tick <= self.current_tick <= event.end_tick:
                # Find track center
                base = event.track_id.replace("_FWD", "").replace("_REV", "")
                parts = base.split("_")
                if len(parts) >= 3:
                    u, v = parts[1], parts[2]
                    if u in NODE_COORDINATES and v in NODE_COORDINATES:
                        x1, y1 = self._transform_coords(*NODE_COORDINATES[u])
                        x2, y2 = self._transform_coords(*NODE_COORDINATES[v])
                        mx, my = (x1 + x2) / 2, (y1 + y2) / 2

                        # Warning triangle
                        size = 12 * self.scale_factor
                        pulse = abs(math.sin(self.current_tick * 0.3)) * 3 * self.scale_factor
                        self.canvas.create_polygon(mx, my - size - pulse,
                                                   mx - size, my + size - pulse,
                                                   mx + size, my + size - pulse,
                                                   fill=Colors.FOREIGN_OBJECT, outline="#fff", width=max(1, 1.5 * self.scale_factor),
                                                   tags="dynamic_overlay")
                        font_size = max(5, int(6 * self.scale_factor))
                        self.canvas.create_text(mx, my + size + 14 * self.scale_factor, text=event.object_type[:4],
                                                font=("Segoe UI", font_size, "bold"), fill=Colors.FOREIGN_OBJECT,
                                                tags="dynamic_overlay")

    def _highlight_track(self, track_id: str):
        if self.scale_factor <= 0:
            return
        base = track_id.replace("_FWD", "").replace("_REV", "")
        parts = base.split("_")
        if len(parts) >= 3:
            u, v = parts[1], parts[2]
            if u in NODE_COORDINATES and v in NODE_COORDINATES:
                x1, y1 = self._transform_coords(*NODE_COORDINATES[u])
                x2, y2 = self._transform_coords(*NODE_COORDINATES[v])
                # Draw highlight glow
                for offset in [-8, 8]:
                    dx, dy = x2 - x1, y2 - y1
                    dist = math.hypot(dx, dy)
                    if dist == 0: continue
                    ux, uy = dx / dist, dy / dist
                    nx, ny = -uy, ux
                    trim = (NODE_RADIUS + 8) * self.scale_factor
                    off = offset * self.scale_factor
                    x1s = x1 + ux * trim + nx * off
                    y1s = y1 + uy * trim + ny * off
                    x2s = x2 - ux * trim + nx * off
                    y2s = y2 - uy * trim + ny * off
                    self.canvas.create_line(x1s, y1s, x2s, y2s, fill=Colors.ACCENT_CYAN, width=max(2, 3 * self.scale_factor),
                                            tags="dynamic_overlay")

    def _highlight_node(self, node_id: str):
        if self.scale_factor <= 0 or node_id not in NODE_COORDINATES:
            return
        tx, ty = self._transform_coords(*NODE_COORDINATES[node_id])
        r = (NODE_RADIUS + 6) * self.scale_factor
        pulse = abs(math.sin(self.current_tick * 0.15)) * 3 * self.scale_factor
        self.canvas.create_oval(tx-r-pulse, ty-r-pulse, tx+r+pulse, ty+r+pulse,
                                    outline=Colors.ACCENT_CYAN, width=2, tags="dynamic_overlay")

    # =========================================================================
    # BAG STATE APPROXIMATION
    # =========================================================================

    def _update_bag_approximations(self, tick_data: dict):
        """Approximate bag positions from edge occupancy."""
        # This is a simplified reconstruction - real positions need evaluator state
        pass

    # =========================================================================
    # KPI PANEL UPDATES
    # =========================================================================

    def _update_kpi_panel(self):
        # Use actual bag telemetry for real-time KPIs during playback
        if self.bag_history and self.bag_arrival_ticks:
            # Cumulative delivered: count bags with arrival_tick <= current_tick
            delivered = sum(1 for at in self.bag_arrival_ticks.values() if at <= self.current_tick)

            # Cumulative misrouted: delivered bags that missed deadline
            misrouted = 0
            total_transit = 0
            for bag_id, arrival_tick in self.bag_arrival_ticks.items():
                if arrival_tick <= self.current_tick:
                    release_tick = self.bag_release_ticks.get(bag_id, arrival_tick)
                    deadline_tick = self.bag_deadline_ticks.get(bag_id)
                    transit = arrival_tick - release_tick
                    total_transit += transit
                    if deadline_tick and arrival_tick > deadline_tick:
                        misrouted += 1

            # In-transit: bags released but not yet arrived at current_tick
            # Use the most recent tick's data for in-transit count
            available_ticks = [t for t in self.bag_history.keys() if t <= self.current_tick]
            in_transit = 0
            if available_ticks:
                tick_to_use = max(available_ticks)
                tick_bags = self.bag_history[tick_to_use]
                for bag_id, bag_data in tick_bags.items():
                    arrival_tick = bag_data.get("arrival_tick")
                    release_tick = bag_data.get("release_tick")
                    current_node = bag_data.get("current_node")
                    # In transit if released, not arrived, and has a current position
                    if arrival_tick is None and current_node is not None and release_tick <= self.current_tick:
                        in_transit += 1

            mean_latency = (total_transit / delivered) if delivered else 0.0

        # Fallback: at end of simulation, use evaluator summary if bag telemetry not available
        elif self.last_simulation_summary and self.current_tick >= self.max_ticks:
            misrouted = self.last_simulation_summary.get("misrouted_bags", 0)
            mean_latency = self.last_simulation_summary.get("mean_delivery_latency", 0.0)
            delivered = self.last_simulation_summary.get("delivered_bags", 0)
            in_transit = 0
        else:
            # No telemetry available yet
            delivered = 0
            misrouted = 0
            mean_latency = 0.0
            in_transit = 0

        # Suspicious count (only in-transit at current tick) - from detector (detection feature)
        sus_count = 0
        if self.suspicious_detector:
            for bag_id in self.suspicious_detector.suspicious_bags:
                node, edge, arrival = self.suspicious_detector.get_bag_state_at_tick(bag_id, self.current_tick)
                if node is not None and arrival is None:
                    sus_count += 1

        # Foreign object count - recompute active from pre-defined scenarios
        fo_count = 0
        for event in self.foreign_detector.events:
            if event.start_tick <= self.current_tick <= event.end_tick:
                fo_count += 1

        # Diverted count: bags marked as diverted in telemetry
        diverted = 0
        available_ticks = [t for t in self.bag_history.keys() if t <= self.current_tick]
        if available_ticks:
            tick_to_use = max(available_ticks)
            tick_bags = self.bag_history[tick_to_use]
            for bag_id, bag_data in tick_bags.items():
                if bag_data.get("diverted", False):
                    diverted += 1

        # Update cards
        self.kpi_cards["misrouted"]["value"].config(text=str(misrouted))
        self.kpi_cards["mean_latency"]["value"].config(text=f"{mean_latency:.1f} ticks")
        self.kpi_cards["in_transit"]["value"].config(text=str(in_transit))
        self.kpi_cards["delivered"]["value"].config(text=str(delivered))
        self.kpi_cards["diverted"]["value"].config(text=str(diverted))
        self.kpi_cards["suspicious"]["value"].config(text=str(sus_count))
        self.kpi_cards["foreign_objects"]["value"].config(text=str(fo_count))

        # Update summary
        jam_count = sum(1 for d in self.history.get(self.current_tick, {}).values() if d.get("status") == "JAMMED")
        self.lbl_active_summary.config(
            text=f"ACTIVE: {jam_count} JAMS | {sus_count} SUSPICIOUS | {fo_count} FOREIGN"
        )

    def _update_phase_indicator(self):
        for phase in PHASES:
            if phase["start"] <= self.current_tick <= phase["end"]:
                self.lbl_phase.config(text=f"PHASE: {phase['label']}", fg=phase["color"])
                break

    def _update_playback_status(self):
        if self.is_playing:
            self.lbl_playback_status.config(text=f"PLAYING @ {self.playback_speed:.2f}×", fg=Colors.ACCENT_GREEN)
            self.btn_play.config(text="⏸ PAUSE", bg=Colors.ACCENT_ORANGE)
        else:
            self.lbl_playback_status.config(text="PAUSED", fg=Colors.FG_SECONDARY)
            self.btn_play.config(text="▶ PLAY", bg=Colors.ACCENT_GREEN)

    def _update_tick_counter(self):
        self.lbl_tick_counter.config(text=f"TICK: {self.current_tick:04d} / {self.max_ticks:04d}")

    # =========================================================================
    # ALERT LOG
    # =========================================================================

    def _get_alerts_for_tick(self, tick: int) -> List[AlertEvent]:
        """Get all alerts (jams, suspicious, foreign objects) for a specific tick."""
        alerts = []

        # 1. Jam alerts from telemetry
        tick_data = self.history.get(tick, {})
        for edge_id, data in tick_data.items():
            if data.get("status") == "JAMMED":
                base = edge_id.replace("_FWD", "").replace("_REV", "")
                alerts.append(AlertEvent(
                    tick=tick,
                    track_id=base,
                    zone=self._get_zone_for_track(base),
                    description=f"JAM: {data.get('fault_reason', 'UNKNOWN')} on {base}",
                    severity="CRITICAL",
                    status="ACTIVE",
                    event_type="JAM"
                ))

        # 2. Suspicious bag alerts (precomputed)
        if self.suspicious_detector:
            alerts.extend(self.suspicious_detector.precomputed_alerts.get(tick, []))

        # 3. Foreign object alerts (compute from scenarios)
        for event in self.foreign_detector.events:
            if event.start_tick == tick:
                alerts.append(AlertEvent(
                    tick=tick,
                    track_id=event.track_id,
                    zone=event.zone,
                    description=f"Foreign object detected: {event.object_type} — {event.description}",
                    severity=event.severity,
                    status="ACTIVE",
                    event_type="FOREIGN_OBJECT"
                ))
            elif event.end_tick == tick:
                alerts.append(AlertEvent(
                    tick=tick,
                    track_id=event.track_id,
                    zone=event.zone,
                    description=f"Foreign object cleared: {event.object_type} — Track restored",
                    severity="INFO",
                    status="RESOLVED",
                    event_type="FOREIGN_OBJECT"
                ))

        return alerts

    def _get_zone_for_track(self, track_id: str) -> str:
        base = track_id.replace("_FWD", "").replace("_REV", "")
        parts = base.split("_")
        if len(parts) >= 3:
            from_node = parts[1]
            ntype = NODE_TYPES.get(from_node, "unknown")
            if ntype == "intake": return "INTAKE_ZONE"
            elif ntype == "junction": return "JUNCTION_ZONE"
            elif ntype == "spine": return "SPINE_ZONE"
            elif ntype == "gate": return "GATE_ZONE"
        return "UNKNOWN_ZONE"

    def _update_alert_list(self):
        # Get alerts for current tick
        current_alerts = self._get_alerts_for_tick(self.current_tick)

        # Add new alerts to running history (deduplicated by unique key)
        for alert in current_alerts:
            key = (alert.tick, alert.track_id, alert.event_type, alert.description[:50])
            if key not in self.seen_alert_keys:
                self.seen_alert_keys.add(key)
                self.all_alerts.append(alert)

        # Filter alerts from running history
        filter_val = self.alert_filter.get()
        filtered = []

        for alert in self.all_alerts:
            if filter_val == "ALL":
                filtered.append(alert)
            elif filter_val == "CRITICAL" and alert.severity in ("CRITICAL", "EMERGENCY"):
                filtered.append(alert)
            elif filter_val == "WARNING" and alert.severity == "WARNING":
                filtered.append(alert)
            elif filter_val == "INFO" and alert.severity == "INFO":
                filtered.append(alert)
            elif filter_val == "SUSPICIOUS" and alert.event_type == "SUSPICIOUS_BAG":
                filtered.append(alert)
            elif filter_val == "FOREIGN" and alert.event_type == "FOREIGN_OBJECT":
                filtered.append(alert)
            elif filter_val == "DIVERSION" and alert.event_type == "DIVERSION":
                filtered.append(alert)

        # Sort by tick descending (newest first)
        filtered.sort(key=lambda a: a.tick, reverse=True)

        # Update treeview
        self.alert_tree.delete(*self.alert_tree.get_children())
        for alert in filtered[:500]:  # Limit display
            sev_tag = alert.severity
            if alert.event_type == "SUSPICIOUS_BAG":
                sev_tag = "SUSPICIOUS"
            elif alert.event_type == "FOREIGN_OBJECT":
                sev_tag = "FOREIGN"
            elif alert.event_type == "DIVERSION":
                sev_tag = "DIVERSION"

            track_display = alert.track_id.replace("_FWD", "").replace("_REV", "")
            if len(track_display) > 18:
                track_display = track_display[:15] + "..."

            desc = alert.description
            if len(desc) > 50:
                desc = desc[:47] + "..."

            self.alert_tree.insert("", tk.END, values=(
                alert.tick, alert.severity, track_display, desc
            ), tags=(sev_tag, alert.event_type))

        # Count active for current tick
        active = sum(1 for a in current_alerts if a.status == "ACTIVE")
        self.lbl_alert_count.config(text=f"{active} ACTIVE")

    def _refresh_alert_list(self):
        self._update_alert_list()

    # =========================================================================
    # INSPECTOR PANEL
    # =========================================================================

    def _show_track_inspector(self, track_id: str):
        self.inspect_placeholder.pack_forget()
        self.inspect_detail_frame.pack(fill=tk.BOTH, expand=True)
        for w in self.inspect_detail_frame.winfo_children():
            w.destroy()

        base = track_id.replace("_FWD", "").replace("_REV", "")
        parts = base.split("_")
        if len(parts) < 3:
            return
        u, v = parts[1], parts[2]

        # Get stats
        stats = self.track_stats.get(base, {})
        tick_data = self.history.get(self.current_tick, {})
        edge_data = tick_data.get(base + "_FWD", {}) or tick_data.get(base + "_REV", {})

        self.inspect_title.config(text=f"TRACK: {base}  ({u} → {v})")

        # Current state
        state_frame = tk.LabelFrame(self.inspect_detail_frame, text="CURRENT STATE",
                                     bg=Colors.BG_CARD, fg=Colors.ACCENT_CYAN, font=("Segoe UI", 8, "bold"))
        state_frame.pack(fill=tk.X, pady=4, padx=4)

        curr_status = edge_data.get("status", "OPERATIONAL")
        curr_bags = edge_data.get("active_bags", 0)
        curr_fault = edge_data.get("fault_reason", "NONE")
        wear = edge_data.get("volume", 0)

        # Wear threshold from layout
        wear_threshold = 0
        for edge in self.layout_data["edges"]:
            if edge["id"] == base:
                wear_threshold = edge["wear_threshold"]
                break

        wear_pct = (wear / wear_threshold * 100) if wear_threshold > 0 else 0

        info_items = [
            ("STATUS", curr_status, Colors.JAMMED if curr_status == "JAMMED" else Colors.ACCENT_GREEN),
            ("ACTIVE BAGS", str(curr_bags), Colors.ACCENT_ORANGE if curr_bags > 5 else Colors.FG_PRIMARY),
            ("FAULT REASON", curr_fault, Colors.ACCENT_RED if curr_fault != "NONE" else Colors.FG_MUTED),
            ("CUMULATIVE VOLUME", f"{wear:,}", Colors.ACCENT_AMBER if wear_pct > 80 else Colors.FG_PRIMARY),
            ("WEAR THRESHOLD", f"{wear_threshold:,}", Colors.FG_SECONDARY),
            ("WEAR LEVEL", f"{wear_pct:.1f}%", Colors.ACCENT_RED if wear_pct >= 100 else (Colors.ACCENT_ORANGE if wear_pct > 80 else Colors.ACCENT_GREEN)),
        ]

        for i, (label, val, color) in enumerate(info_items):
            tk.Label(state_frame, text=label, font=("Segoe UI", 7), fg=Colors.FG_MUTED, bg=Colors.BG_CARD).grid(row=i, column=0, sticky=tk.W, padx=8, pady=2)
            tk.Label(state_frame, text=val, font=("Consolas", 9, "bold"), fg=color, bg=Colors.BG_CARD).grid(row=i, column=1, sticky=tk.W, padx=8, pady=2)

        # Wear bar
        bar_frame = tk.Frame(state_frame, bg=Colors.BG_CARD)
        bar_frame.grid(row=len(info_items), column=0, columnspan=2, sticky=tk.EW, padx=8, pady=6)
        bar_bg = tk.Frame(bar_frame, bg="#2a2a35", height=8)
        bar_bg.pack(fill=tk.X)
        bar_fill = tk.Frame(bar_bg, bg=Colors.ACCENT_RED if wear_pct >= 100 else (Colors.ACCENT_ORANGE if wear_pct > 80 else Colors.ACCENT_GREEN), height=8)
        bar_fill.place(relx=0, rely=0, relwidth=min(wear_pct/100, 1.0), relheight=1)

        # Historical stats
        hist_frame = tk.LabelFrame(self.inspect_detail_frame, text="HISTORICAL STATISTICS",
                                    bg=Colors.BG_CARD, fg=Colors.ACCENT_CYAN, font=("Segoe UI", 8, "bold"))
        hist_frame.pack(fill=tk.X, pady=4, padx=4)

        hist_items = [
            ("TOTAL BAGS PROCESSED", f"{stats.get('total_bags', 0):,}"),
            ("PEAK OCCUPANCY", str(stats.get('max_occupancy', 0))),
            ("JAM INCIDENTS", str(stats.get('jam_count', 0))),
        ]
        for i, (label, val) in enumerate(hist_items):
            tk.Label(hist_frame, text=label, font=("Segoe UI", 7), fg=Colors.FG_MUTED, bg=Colors.BG_CARD).grid(row=i, column=0, sticky=tk.W, padx=8, pady=2)
            tk.Label(hist_frame, text=val, font=("Consolas", 9, "bold"), fg=Colors.FG_PRIMARY, bg=Colors.BG_CARD).grid(row=i, column=1, sticky=tk.W, padx=8, pady=2)

        # Jam history
        jam_frame = tk.LabelFrame(self.inspect_detail_frame, text="JAM HISTORY",
                                   bg=Colors.BG_CARD, fg=Colors.ACCENT_CYAN, font=("Segoe UI", 8, "bold"))
        jam_frame.pack(fill=tk.BOTH, expand=True, pady=4, padx=4)

        # Find jams for this track
        jams = []
        for tick in range(1, self.current_tick + 1):
            td = self.history.get(tick, {})
            for eid, ed in td.items():
                if eid.replace("_FWD", "").replace("_REV", "") == base and ed.get("status") == "JAMMED":
                    jams.append((tick, ed.get("fault_reason", "UNKNOWN")))

        if jams:
            # Group consecutive
            grouped = []
            current = None
            for tick, reason in jams:
                if current and tick == current[1] + 1 and reason == current[2]:
                    current = (current[0], tick, reason)
                else:
                    if current: grouped.append(current)
                    current = (tick, tick, reason)
            if current: grouped.append(current)

            for start, end, reason in grouped[-10:]:  # Show last 10
                dur = end - start + 1
                row = tk.Frame(jam_frame, bg=Colors.BG_CARD)
                row.pack(fill=tk.X, padx=8, pady=1)
                tk.Label(row, text=f"T{start:04d}–T{end:04d} ({dur} ticks)", font=("Consolas", 7), fg=Colors.ACCENT_RED, bg=Colors.BG_CARD).pack(side=tk.LEFT)
                tk.Label(row, text=reason, font=("Segoe UI", 7), fg=Colors.FG_SECONDARY, bg=Colors.BG_CARD).pack(side=tk.LEFT, padx=8)
        else:
            tk.Label(jam_frame, text="No jam history", font=("Segoe UI", 8), fg=Colors.FG_MUTED, bg=Colors.BG_CARD).pack(pady=8)

    def _show_node_inspector(self, node_id: str):
        self.inspect_placeholder.pack_forget()
        self.inspect_detail_frame.pack(fill=tk.BOTH, expand=True)
        for w in self.inspect_detail_frame.winfo_children():
            w.destroy()

        ntype = NODE_TYPES.get(node_id, "unknown")
        label = NODE_TYPE_LABELS.get(ntype, "UNKNOWN")

        self.inspect_title.config(text=f"NODE: {node_id}  ({label})")

        # Connections
        conn_frame = tk.LabelFrame(self.inspect_detail_frame, text="CONNECTIONS",
                                    bg=Colors.BG_CARD, fg=Colors.ACCENT_CYAN, font=("Segoe UI", 8, "bold"))
        conn_frame.pack(fill=tk.X, pady=4, padx=4)

        outgoing = []
        incoming = []
        for u, v in EDGE_CONNECTIONS:
            if u == node_id:
                outgoing.append(v)
            if v == node_id:
                incoming.append(u)

        tk.Label(conn_frame, text="OUTGOING:", font=("Segoe UI", 7, "bold"), fg=Colors.ACCENT_GREEN, bg=Colors.BG_CARD).pack(anchor=tk.W, padx=8, pady=2)
        tk.Label(conn_frame, text="  " + ", ".join(outgoing) if outgoing else "  (none)", font=("Segoe UI", 7), fg=Colors.FG_PRIMARY, bg=Colors.BG_CARD).pack(anchor=tk.W, padx=16)
        tk.Label(conn_frame, text="INCOMING:", font=("Segoe UI", 7, "bold"), fg=Colors.ACCENT_BLUE, bg=Colors.BG_CARD).pack(anchor=tk.W, padx=8, pady=2)
        tk.Label(conn_frame, text="  " + ", ".join(incoming) if incoming else "  (none)", font=("Segoe UI", 7), fg=Colors.FG_PRIMARY, bg=Colors.BG_CARD).pack(anchor=tk.W, padx=16)

        # Throughput
        tp_frame = tk.LabelFrame(self.inspect_detail_frame, text="THROUGHPUT (CURRENT TICK)",
                                  bg=Colors.BG_CARD, fg=Colors.ACCENT_CYAN, font=("Segoe UI", 8, "bold"))
        tp_frame.pack(fill=tk.X, pady=4, padx=4)

        tick_data = self.history.get(self.current_tick, {})
        total_out = 0
        total_in = 0
        for edge_id, data in tick_data.items():
            base = edge_id.replace("_FWD", "").replace("_REV", "")
            parts = base.split("_")
            if len(parts) >= 3:
                u, v = parts[1], parts[2]
                bags = data.get("active_bags", 0)
                if u == node_id:
                    total_out += bags
                if v == node_id:
                    total_in += bags

        tk.Label(tp_frame, text=f"OUTBOUND BAGS: {total_out}", font=("Consolas", 10, "bold"), fg=Colors.ACCENT_GREEN, bg=Colors.BG_CARD).pack(anchor=tk.W, padx=8, pady=2)
        tk.Label(tp_frame, text=f"INBOUND BAGS: {total_in}", font=("Consolas", 10, "bold"), fg=Colors.ACCENT_BLUE, bg=Colors.BG_CARD).pack(anchor=tk.W, padx=8, pady=2)

        # Active alerts for this node
        alert_frame = tk.LabelFrame(self.inspect_detail_frame, text="ACTIVE ALERTS",
                                     bg=Colors.BG_CARD, fg=Colors.ACCENT_CYAN, font=("Segoe UI", 8, "bold"))
        alert_frame.pack(fill=tk.BOTH, expand=True, pady=4, padx=4)

        node_alerts = [a for a in self.all_alerts if a.status == "ACTIVE" and
                       (node_id in a.track_id or self._node_in_zone(node_id, a.zone))]

        if node_alerts:
            for alert in node_alerts[:5]:
                row = tk.Frame(alert_frame, bg=Colors.BG_CARD)
                row.pack(fill=tk.X, padx=8, pady=2)
                sev_color = {"CRITICAL": Colors.ACCENT_RED, "EMERGENCY": Colors.ACCENT_RED,
                            "WARNING": Colors.ACCENT_ORANGE, "INFO": Colors.ACCENT_BLUE}.get(alert.severity, Colors.FG_PRIMARY)
                tk.Label(row, text=f"[{alert.severity}]", font=("Consolas", 7, "bold"), fg=sev_color, bg=Colors.BG_CARD).pack(side=tk.LEFT)
                tk.Label(row, text=f"T{alert.tick:04d} {alert.description[:40]}", font=("Segoe UI", 7), fg=Colors.FG_PRIMARY, bg=Colors.BG_CARD).pack(side=tk.LEFT, padx=6)
        else:
            tk.Label(alert_frame, text="No active alerts", font=("Segoe UI", 8), fg=Colors.FG_MUTED, bg=Colors.BG_CARD).pack(pady=8)

    def _show_bag_inspector(self, bag_id: str):
        self.inspect_placeholder.pack_forget()
        self.inspect_detail_frame.pack(fill=tk.BOTH, expand=True)
        for w in self.inspect_detail_frame.winfo_children():
            w.destroy()

        bag = self.bag_states.get(bag_id)
        if not bag:
            return

        sus = self.suspicious_detector.bags.get(bag_id) if self.suspicious_detector else None
        is_sus = sus and sus.is_suspicious

        self.inspect_title.config(text=f"BAG: {bag_id}" + (" ⚠ SUSPICIOUS" if is_sus else ""))

        # Basic info
        info_frame = tk.LabelFrame(self.inspect_detail_frame, text="BAG INFORMATION",
                                    bg=Colors.BG_CARD, fg=Colors.ACCENT_CYAN, font=("Segoe UI", 8, "bold"))
        info_frame.pack(fill=tk.X, pady=4, padx=4)

        items = [
            ("INTAKE", bag.intake_node),
            ("DESTINATION", bag.destination_gate),
            ("RELEASE TICK", str(bag.release_tick)),
            ("DEADLINE", str(bag.deadline_tick) if bag.deadline_tick else "NONE"),
            ("STATUS", "DELIVERED" if bag.arrival_tick else ("IN TRANSIT" if bag.release_tick <= self.current_tick else "PENDING")),
            ("TRANSIT TIME", f"{bag.transit_time} ticks" if bag.transit_time else "N/A"),
        ]

        # Add diversion info if applicable
        diverted = getattr(bag, 'diverted', False)
        diversion_tick = getattr(bag, 'diversion_tick', None)
        if diverted:
            items.append(("DIVERTED", "YES"))
            if diversion_tick:
                items.append(("DIVERSION TICK", str(diversion_tick)))

        for i, (label, val) in enumerate(items):
            tk.Label(info_frame, text=label, font=("Segoe UI", 7), fg=Colors.FG_MUTED, bg=Colors.BG_CARD).grid(row=i, column=0, sticky=tk.W, padx=8, pady=2)
            color = Colors.ACCENT_RED if label == "STATUS" and val == "DELIVERED" and bag.is_misrouted else Colors.FG_PRIMARY
            tk.Label(info_frame, text=val, font=("Consolas", 9, "bold"), fg=color, bg=Colors.BG_CARD).grid(row=i, column=1, sticky=tk.W, padx=8, pady=2)

        # Suspicious reasons
        if is_sus:
            sus_frame = tk.LabelFrame(self.inspect_detail_frame, text="SUSPICIOUS DETECTION REASONS",
                                       bg=Colors.BG_CARD, fg=Colors.ACCENT_PURPLE, font=("Segoe UI", 8, "bold"))
            sus_frame.pack(fill=tk.X, pady=4, padx=4)
            for reason in sus.suspicious_reasons:
                tk.Label(sus_frame, text="▸ " + reason.replace("_", " ").title(), font=("Segoe UI", 7),
                         fg=Colors.ACCENT_PURPLE, bg=Colors.BG_CARD).pack(anchor=tk.W, padx=8, pady=1)

        # Route history
        hist_frame = tk.LabelFrame(self.inspect_detail_frame, text="ROUTE HISTORY",
                                    bg=Colors.BG_CARD, fg=Colors.ACCENT_CYAN, font=("Segoe UI", 8, "bold"))
        hist_frame.pack(fill=tk.BOTH, expand=True, pady=4, padx=4)

        if bag.history:
            for node, tick in bag.history[-15:]:  # Last 15 hops
                row = tk.Frame(hist_frame, bg=Colors.BG_CARD)
                row.pack(fill=tk.X, padx=8, pady=1)
                ntype = NODE_TYPES.get(node, "?")
                type_tag = NODE_TYPE_LABELS.get(ntype, "?")[:3]
                tk.Label(row, text=f"T{tick:04d}", font=("Consolas", 7), fg=Colors.FG_SECONDARY, bg=Colors.BG_CARD, width=8).pack(side=tk.LEFT)
                tk.Label(row, text=f"[{type_tag}]", font=("Consolas", 7, "bold"), fg=Colors.ACCENT_CYAN, bg=Colors.BG_CARD, width=6).pack(side=tk.LEFT)
                tk.Label(row, text=node, font=("Consolas", 8, "bold"), fg=Colors.FG_PRIMARY, bg=Colors.BG_CARD).pack(side=tk.LEFT)
        else:
            tk.Label(hist_frame, text="No route history available", font=("Segoe UI", 8), fg=Colors.FG_MUTED, bg=Colors.BG_CARD).pack(pady=8)

    def _node_in_zone(self, node: str, zone: str) -> bool:
        ntype = NODE_TYPES.get(node, "")
        if zone == "INTAKE_ZONE" and ntype == "intake": return True
        if zone == "JUNCTION_ZONE" and ntype == "junction": return True
        if zone == "SPINE_ZONE" and ntype == "spine": return True
        if zone == "GATE_ZONE" and ntype == "gate": return True
        return False

    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================

    def _on_canvas_click(self, event):
        # Convert window coordinates to canvas coordinates
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)

        # Convert to network coordinates (inverse transform)
        if self.scale_factor > 0:
            x = self._inverse_transform_x(cx)
            y = self._inverse_transform_y(cy)
        else:
            x, y = cx, cy

        # Check node click
        for node_id, (nx, ny) in NODE_COORDINATES.items():
            if (x - nx) ** 2 + (y - ny) ** 2 <= (NODE_RADIUS + 10) ** 2:
                self.selected_node = node_id
                self.selected_track = None
                self.selected_bag = None
                self._show_node_inspector(node_id)
                return

        # Check track click (simplified - check distance to line)
        closest_track = None
        min_dist = float('inf')

        for u, v in EDGE_CONNECTIONS:
            if u in NODE_COORDINATES and v in NODE_COORDINATES:
                x1, y1 = NODE_COORDINATES[u]
                x2, y2 = NODE_COORDINATES[v]
                dist = self._point_to_line_dist(x, y, x1, y1, x2, y2)
                if dist < min_dist and dist < 15:
                    min_dist = dist
                    closest_track = f"e_{u}_{v}"

        if closest_track:
            self.selected_track = closest_track
            self.selected_node = None
            self.selected_bag = None
            self._show_track_inspector(closest_track)
            return

        # Check suspicious bag badge click
        if self.suspicious_detector:
            for bag_id in self.suspicious_detector.suspicious_bags:
                bag = self.suspicious_detector.bags.get(bag_id)
                if bag and bag.current_node in NODE_COORDINATES:
                    bx, by = NODE_COORDINATES[bag.current_node]
                    if (x - bx) ** 2 + (y - by) ** 2 <= (NODE_RADIUS + 20) ** 2:
                        self.selected_bag = bag_id
                        self.selected_track = None
                        self.selected_node = None
                        self._show_bag_inspector(bag_id)
                        return

    def _on_canvas_hover(self, event):
        # Convert window coordinates to canvas coordinates (accounting for scroll)
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        # Tooltip-like behavior could be added here using x, y
        pass

    def _on_canvas_leave(self, event):
        pass

    def _point_to_line_dist(self, px, py, x1, y1, x2, y2):
        # Distance from point to line segment
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1)
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy
        return math.hypot(px - closest_x, py - closest_y)

    def _on_alert_select(self, event):
        selection = self.alert_tree.selection()
        if selection:
            item = self.alert_tree.item(selection[0])
            vals = item['values']
            if vals:
                tick = int(vals[0])
                track = vals[2]
                # Jump to that tick
                self.current_tick = tick
                self.sub_tick = 0
                self._update_display()
                # Select the track
                if track != "UNKNOWN":
                    self.selected_track = track
                    self._show_track_inspector(track)

    # =========================================================================
    # PLAYBACK CONTROLS
    # =========================================================================

    def _on_slider_scrub(self, val):
        if self.updating_via_slider:
            return
        self.current_tick = int(val)
        self.sub_tick = 0
        self._update_display()

    def _on_speed_change(self, val):
        self.playback_speed = float(val)
        self.lbl_speed.config(text=f"{self.playback_speed:.2f}×")

    def _toggle_playback(self):
        self.is_playing = not self.is_playing
        if self.is_playing:
            self._playback_loop()
        self._update_playback_status()

    def _playback_loop(self):
        if not self.is_playing:
            return

        self.sub_tick += 1
        if self.sub_tick >= SUB_FRAMES_PER_TICK:
            self.sub_tick = 0
            if self.current_tick < self.max_ticks:
                self.current_tick += 1
            else:
                self.is_playing = False
                self._update_playback_status()
                return

        self._update_display()
        delay = int(REFRESH_RATE_MS / self.playback_speed)
        self.root.after(max(1, delay), self._playback_loop)

    def _next_tick(self):
        if self.current_tick < self.max_ticks:
            self.is_playing = False
            self.sub_tick = 0
            self.current_tick += 1
            self._update_display()
            self._update_playback_status()

    def _prev_tick(self):
        if self.current_tick > 1:
            self.is_playing = False
            self.sub_tick = 0
            self.current_tick -= 1
            self._update_display()
            self._update_playback_status()

    def _speed_up(self):
        self.playback_speed = min(4.0, self.playback_speed + 0.25)
        self.speed_var.set(self.playback_speed)
        self.lbl_speed.config(text=f"{self.playback_speed:.2f}×")

    def _slow_down(self):
        self.playback_speed = max(0.25, self.playback_speed - 0.25)
        self.speed_var.set(self.playback_speed)
        self.lbl_speed.config(text=f"{self.playback_speed:.2f}×")

    def _run_simulation(self):
        """Run simulation with selected scenario and solution in background thread."""
        if self.simulation_running:
            return

        scenario_name = self.scenario_var.get()
        solution_name = self.solution_var.get()

        # Map solution name to module
        solution_module = oursolution if solution_name == "optimized" else solution

        # Disable UI during simulation
        self.simulation_running = True
        self.btn_run.config(state=tk.DISABLED, text="⏳ RUNNING...", bg=Colors.ACCENT_AMBER)
        self.lbl_run_status.config(text=f"Running {scenario_name} / {solution_name}...", fg=Colors.ACCENT_ORANGE)
        self.scenario_combo.config(state=tk.DISABLED)
        self.solution_combo.config(state=tk.DISABLED)

        # Cache directory for telemetry files
        cache_dir = BASE_DIR / "dashboard_cache"
        cache_dir.mkdir(exist_ok=True)
        telemetry_filename = f"live_telemetry_{scenario_name}_{solution_name}.csv"
        telemetry_path = cache_dir / telemetry_filename
        bag_telemetry_filename = f"live_bag_telemetry_{scenario_name}_{solution_name}.csv"
        bag_telemetry_path = cache_dir / bag_telemetry_filename

        def run_in_thread():
            try:
                # Run the experiment
                scenario_config = SCENARIOS[scenario_name]
                config = ExperimentConfig(
                    experiment_id=f"dashboard_{scenario_name}_{solution_name}",
                    scenario_name=scenario_name,
                    seed=42,
                    bag_volume_multiplier=scenario_config["bag_volume_multiplier"],
                    additional_jams=scenario_config.get("additional_jams", []),
                    foreign_object_scenarios=scenario_config.get("foreign_object_scenarios", []),
                    diversion_threshold=scenario_config.get("diversion_threshold", 0.7),
                    diversion_capacity=scenario_config.get("diversion_capacity", 50),
                    diversion_node=scenario_config.get("diversion_node", "DIVERSION_INSPECTION"),
                )

                evaluator = run_experiment(
                    config=config,
                    layout_path=BASE_DIR / "data" / "network_layout.json",
                    base_scenario_path=BASE_DIR / "data" / "simulation_scenario.json",
                    output_dir=BASE_DIR / "experiment_output" / "dashboard_runs",
                    routing_module=solution_module
                )

                # Capture the evaluator's actual summary (ground truth metrics)
                summary = evaluator.get_summary()
                summary_dict = {
                    "total_bags": summary.total_bags,
                    "delivered_bags": summary.delivered_bags,
                    "stranded_bags": summary.stranded_bags,
                    "misrouted_bags": summary.misrouted_bags,
                    "mean_delivery_latency": summary.mean_delivery_latency,
                    "total_jams_triggered": summary.total_jams_triggered,
                }

                # Copy the generated telemetry to our unique filename
                # The evaluator writes telemetry to BASE_DIR / "live_telemetry.csv" by default
                generated_telemetry = BASE_DIR / "live_telemetry.csv"
                generated_bag_telemetry = BASE_DIR / "live_bag_telemetry.csv"
                if generated_telemetry.exists():
                    import shutil
                    shutil.copy2(generated_telemetry, telemetry_path)
                    self.current_telemetry_path = telemetry_path
                    print(f"Telemetry saved to {telemetry_path}")
                    # Also copy bag telemetry
                    if generated_bag_telemetry.exists():
                        shutil.copy2(generated_bag_telemetry, bag_telemetry_path)
                        self.current_bag_telemetry_path = bag_telemetry_path
                        print(f"Bag telemetry saved to {bag_telemetry_path}")

                # Schedule UI update on main thread with actual summary
                self.root.after(0, lambda: self._on_simulation_complete(scenario_name, solution_name, summary_dict))

            except Exception as e:
                print(f"Simulation error: {e}")
                self.root.after(0, lambda error_msg=str(e): self._on_simulation_error(error_msg))

        # Start background thread
        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()

    def _on_simulation_complete(self, scenario_name: str, solution_name: str, summary_dict: dict = None):
        """Called when simulation completes successfully."""
        # Store actual evaluator summary for KPI display
        if summary_dict:
            self.last_simulation_summary = summary_dict

        # Reload telemetry data
        self._load_telemetry_data()

        # Run detector simulation with the new telemetry data (for suspicious bag detection only)
        if self.suspicious_detector:
            self.suspicious_detector.simulate_with_telemetry(self.history)

        # Reset playback to tick 1
        self.current_tick = 1
        self.sub_tick = 0

        # Update UI
        self._update_display()

        # Re-enable UI
        self.simulation_running = False
        self.btn_run.config(state=tk.NORMAL, text="▶ RUN SIMULATION", bg=Colors.ACCENT_GREEN)
        self.lbl_run_status.config(text=f"Complete: {scenario_name} / {solution_name}", fg=Colors.ACCENT_GREEN)
        self.scenario_combo.config(state="readonly")
        self.solution_combo.config(state="readonly")

    def _on_simulation_error(self, error_msg: str):
        """Called when simulation fails."""
        self.simulation_running = False
        self.btn_run.config(state=tk.NORMAL, text="▶ RUN SIMULATION", bg=Colors.ACCENT_GREEN)
        self.lbl_run_status.config(text=f"Error: {error_msg[:40]}", fg=Colors.ACCENT_RED)
        self.scenario_combo.config(state="readonly")
        self.solution_combo.config(state="readonly")
        messagebox.showerror("Simulation Error", f"Failed to run simulation:\n{error_msg}")

    def _fit_to_view(self):
        """Fit the entire network in view by adjusting scroll region."""
        self.canvas.configure(scrollregion=(-50, -50, 1080, 800))
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

    def _jump_next_event(self):
        """Jump to next tick with any alert/event."""
        for tick in range(self.current_tick + 1, self.max_ticks + 1):
            td = self.history.get(tick, {})
            has_jam = any(d.get("status") == "JAMMED" for d in td.values())
            # Check if any alert exists at this tick
            alerts = self._get_alerts_for_tick(tick)
            if has_jam or alerts:
                self.current_tick = tick
                self.sub_tick = 0
                self._update_display()
                return

    def _jump_prev_event(self):
        """Jump to previous tick with any alert/event."""
        for tick in range(self.current_tick - 1, 0, -1):
            td = self.history.get(tick, {})
            has_jam = any(d.get("status") == "JAMMED" for d in td.values())
            alerts = self._get_alerts_for_tick(tick)
            if has_jam or alerts:
                self.current_tick = tick
                self.sub_tick = 0
                self._update_display()
                return

    def _compute_scale(self):
        """Compute scale factor to fit entire network in canvas with margins."""
        if not hasattr(self, 'canvas') or not self.canvas.winfo_width():
            return

        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()

        # Network bounds (from NODE_COORDINATES)
        min_x = min(c[0] for c in NODE_COORDINATES.values())
        max_x = max(c[0] for c in NODE_COORDINATES.values())
        min_y = min(c[1] for c in NODE_COORDINATES.values())
        max_y = max(c[1] for c in NODE_COORDINATES.values())

        # Add margin for node radius and labels
        margin = NODE_RADIUS + 30
        net_w = max_x - min_x + 2 * margin
        net_h = max_y - min_y + 2 * margin

        # Compute scale to fit with 90% utilization (leave some padding)
        scale_x = (canvas_w * 0.9) / net_w
        scale_y = (canvas_h * 0.9) / net_h
        self.scale_factor = min(scale_x, scale_y, 1.0)  # Don't upscale beyond 1.0

        # Center the network
        self.offset_x = (canvas_w - net_w * self.scale_factor) / 2 - min_x * self.scale_factor + margin * self.scale_factor
        self.offset_y = (canvas_h - net_h * self.scale_factor) / 2 - min_y * self.scale_factor + margin * self.scale_factor

    def _transform_x(self, x):
        return x * self.scale_factor + self.offset_x

    def _transform_y(self, y):
        return y * self.scale_factor + self.offset_y

    def _transform_coords(self, x, y):
        return self._transform_x(x), self._transform_y(y)

    def _inverse_transform_x(self, x):
        if self.scale_factor <= 0:
            return x
        return (x - self.offset_x) / self.scale_factor

    def _inverse_transform_y(self, y):
        if self.scale_factor <= 0:
            return y
        return (y - self.offset_y) / self.scale_factor

    def _inverse_transform_coords(self, x, y):
        return self._inverse_transform_x(x), self._inverse_transform_y(y)

    def _on_canvas_resize(self, event):
        self._compute_scale()
        self._draw_static_network()
        self._update_display()

    def _fit_to_view(self):
        """Fit the entire network in view."""
        self._compute_scale()
        self._draw_static_network()
        self._update_display()


if __name__ == "__main__":
    root = tk.Tk()
    csv_file = BASE_DIR / "live_telemetry.csv"
    app = BSDDashboard(root, telemetry_path=csv_file)
    root.mainloop()