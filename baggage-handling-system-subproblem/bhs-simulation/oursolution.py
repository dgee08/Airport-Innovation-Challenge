import heapq
import json
import os

#tunable parameters for varying seeding
CONGESTION_PENALTY = 2
JAM_PENALTY = 40
WEAR_START = 0.5
WEAR_MAX_PENALTY = 40
WEAR_TRIP_PENALTY = 200
LOOKAHEAD_WEIGHT = 0

#slack = window - elapsed_estimate - remaining_path_cost
LOST_SLACK = -6
TIGHT_SLACK = 5
EASY_SLACK = 20
CONGESTION_EASY = 1.0
CONGESTION_LOST = 1.0

#wear penalty scaling by urgency (ie. urgent bags take shortcuts and relaxed ones take detours)
SCALE_RELAXED = 1.5
SCALE_NORMAL = 1.0
SCALE_TIGHT = 0.5
SCALE_CRITICAL = 0.25
SCALE_LOST = 0.1

# Diversion threshold
DIVERSION_THRESHOLD = 0.7

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_LAYOUT = None
_BAG_INFO = None

_CUMULATIVE = {}
_SEEN = set()
_ELAPSED = {}

def reset():
    _CUMULATIVE.clear()
    _SEEN.clear()
    _ELAPSED.clear()

def _load_layout():
    global _LAYOUT
    if _LAYOUT is not None:
        return _LAYOUT

    layout_path = os.path.join(_DATA_DIR, "network_layout.json")
    with open(layout_path, "r") as f:
        data = json.load(f)

    adj = {n["id"]: [] for n in data["nodes"]}
    edge_map = {}
    cost = {}
    wear = {}
    intake_first_edge = {}
    seen_intake = set()

    for e in data["edges"]:
        u = e["from"]
        v = e["to"]
        eid = e["id"]
        if e.get("bidirectional", False):
            pairs = [(u, v, f"{eid}_FWD"), (v, u, f"{eid}_REV")]
        else:
            pairs = [(u, v, eid)]
        for a, b, sid in pairs:
            adj[a].append(b)
            edge_map[(a, b)] = sid
            cost[sid] = e["base_cost"]
            wear[sid] = e["wear_threshold"]

        if e.get("type") == "intake_feed" and u not in seen_intake:
            seen_intake.add(u)
            intake_first_edge[v] = (eid, e["base_cost"])

    for k in adj:
        adj[k] = sorted(set(adj[k]))

    _LAYOUT = {
        "adj": adj,
        "edge_map": edge_map,
        "cost": cost,
        "wear": wear,
        "intake_first_edge": intake_first_edge,
    }
    return _LAYOUT

def _load_bag_info():
    global _BAG_INFO
    if _BAG_INFO is not None:
        return _BAG_INFO

    info = {}
    path = os.path.join(_DATA_DIR, "simulation_scenario.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            for b in json.load(f).get("bags", []):
                if b.get("deadline_tick") is not None:
                    info[b["bag_id"]] = (b["release_tick"], b["deadline_tick"])
    _BAG_INFO = info
    return info

def _edge_cost(u, v, faults, occupancy, wear_scale, congestion=1.0):
    L = _load_layout()
    eid = L["edge_map"].get((u, v))
    if eid is None:
        return float('inf')

    cost = L["cost"][eid] + (occupancy.get(eid, 0) + 1) * CONGESTION_PENALTY * congestion

    if eid in faults:
        cost += JAM_PENALTY

    limit = L["wear"][eid]
    cumulative = _CUMULATIVE.get(eid, 0)
    if cumulative + 1 >= limit:
        cost += WEAR_TRIP_PENALTY
    else:
        fraction = cumulative / limit
        if fraction > WEAR_START:
            x = (fraction - WEAR_START) / (1.0 - WEAR_START)
            cost += WEAR_MAX_PENALTY * wear_scale * x * x 

    out = L["adj"].get(v, [])
    if out:
        total = sum(occupancy.get(L["edge_map"].get((v, w)), 0) for w in out)
        cost += LOOKAHEAD_WEIGHT * CONGESTION_PENALTY * (total / len(out)) * congestion

    return cost

def _algorithm(src, dst, faults, occupancy, wear_scale, congestion=1.0):
    adj = _load_layout()["adj"]
    dist = {src: 0.0}
    parent = {src: None}
    pq = [(0.0, src)]
    
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, float('inf')):
            continue
        if u == dst:
            break
        for v in adj.get(u, []):
            if v != dst and not adj.get(v):
                continue
            nd = d + _edge_cost(u, v, faults, occupancy, wear_scale, congestion)
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                parent[v] = u
                heapq.heappush(pq, (nd, v))

    if dst not in parent:
        return None, float('inf')
    
    path = [dst]
    while parent[path[-1]] is not None:
        path.append(parent[path[-1]])
    path.reverse()
    return path, dist[dst]

def _pick_tier(bag_id, remaining_cost):
    info = _load_bag_info().get(bag_id)
    if info is None:
        return SCALE_RELAXED, CONGESTION_EASY
    release, deadline = info
    slack = (deadline - release) - _ELAPSED.get(bag_id, 0.0) - remaining_cost
    if slack < LOST_SLACK:
        return SCALE_LOST, CONGESTION_LOST
    if slack < 0:
        return SCALE_CRITICAL, 1.0
    if slack < TIGHT_SLACK:
        return SCALE_TIGHT, 1.0
    if slack < EASY_SLACK:
        return SCALE_NORMAL, 1.0
    return SCALE_NORMAL, CONGESTION_EASY

def route_bag(bag_id, current_node, destination_gate, active_faults, edge_occupancy,
              suspicion_score=0.0, diversion_available=False, diversion_node=None):
    L = _load_layout()
    adj = L["adj"]
    edge_map = L["edge_map"]
    faults = set(active_faults)
    occupancy = edge_occupancy

    if bag_id not in _SEEN:
        _SEEN.add(bag_id)
        first = L["intake_first_edge"].get(current_node)
        if first is not None:
            eid, base = first
            _CUMULATIVE[eid] = _CUMULATIVE.get(eid, 0) + 1
            _ELAPSED[bag_id] = float(base)
        else:
            _ELAPSED[bag_id] = 0.0

    # Diversion logic: if bag is suspicious and diversion is available, route to diversion
    if diversion_available and diversion_node and suspicion_score >= DIVERSION_THRESHOLD:
        # Check if diversion node is a valid neighbor
        if diversion_node in adj.get(current_node, []):
            next = diversion_node
            eid = edge_map[(current_node, next)]
            _CUMULATIVE[eid] = _CUMULATIVE.get(eid, 0) + 1
            L_cost = L["cost"][eid] + (occupancy.get(eid, 0) + 1) * CONGESTION_PENALTY
            _ELAPSED[bag_id] = _ELAPSED.get(bag_id, 0.0) + L_cost
            return next

    neighbors = adj.get(current_node, [])
    if not neighbors:
        return current_node

    path, total = _algorithm(current_node, destination_gate, faults, occupancy, SCALE_NORMAL)
    if path is not None and len(path) > 1:
        scale, cong = _pick_tier(bag_id, total)
        if scale != SCALE_NORMAL or cong != 1.0:
            p2, t2 = _algorithm(current_node, destination_gate, faults, occupancy, scale, congestion=1.0)
            if p2 is not None and len(p2) > 1:
                path, total = p2, t2

    if path is not None and len(path) > 1:
        next = path[1]
    else:
        viable = [v for v in neighbors if v == destination_gate or adj.get(v)] or neighbors
        next = min(viable, key=lambda v: (_edge_cost(current_node, v, faults, occupancy, SCALE_NORMAL), v))

    eid = edge_map[(current_node, next)]
    _CUMULATIVE[eid] = _CUMULATIVE.get(eid, 0) + 1
    L_cost = L["cost"][eid] + (occupancy.get(eid, 0) + 1) * CONGESTION_PENALTY
    _ELAPSED[bag_id] = _ELAPSED.get(bag_id, 0.0) + L_cost

    return next