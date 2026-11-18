# platoon run on the straight town04 highway (stretch A from tools/find_highway.py)
# road 40, lanes 3..6, about 698 m straight, positive lanes drive toward smaller s

MAP = "Town04"     # carla town name, or "xodr:<path>" for a custom opendrive map
DT = 0.1           # must match the bridge fixed_delta_seconds
DURATION = 30.0    # seconds, the leader covers the 698 m stretch in about 35 s at 20 m/s
LOG_DIR = "data/platoon"

# leader spawn point, followers are placed behind it in list order
# use dict(x=.., y=.., z=.., yaw=..) instead for absolute coordinates
SPAWN = dict(road_id=40, lane_id=3, s=150.0)

FALLBACK_TIME = 0.5  # seconds a stale fused estimate may be reused
SAFE_DECEL = -3.0    # m/s^2 once the fallback time runs out
FUSED_BUDGET = 1     # number of fused vehicles the gpu can run (yolo26x is heavy)

VEHICLES = [
    dict(name="leader", role="leader", blueprint="vehicle.lincoln.mkz_2020", lane=3,
         controller="idm", params=dict(v0=20.0),
         lane_change=dict(mode="none")),
    dict(name="f1", role="follower", blueprint="vehicle.tesla.model3", lane=3, gap0=20.0,
         controller="idm", params=dict(v0=25.0, T=1.2, s0=5.0),
         headway_source="gt", lane_change=dict(mode="none"), faults=[]),
    dict(name="f2", role="follower", blueprint="vehicle.tesla.model3", lane=3, gap0=20.0,
         controller="idm", params=dict(v0=25.0, T=1.2, s0=5.0),
         headway_source="gt", lane_change=dict(mode="none"), faults=[]),
    dict(name="f3", role="follower", blueprint="vehicle.tesla.model3", lane=3, gap0=20.0,
         controller="idm", params=dict(v0=25.0, T=1.2, s0=5.0),
         headway_source="gt", lane_change=dict(mode="none"), faults=[]),
]
