from configs import *
import time
class Position:
    def __init__(self, x=0.0, y=0.0):
        self.x, self.y = x, y

class AMR:
    def __init__(self, amr_id, x=0.0, y=0.0):
        self.id = amr_id
        self.status = "idle"    # idle, busy
        self.is_moving = False
        self.is_parked = False
        self.slots = {f"slot_{i}": {"object_id": None, "reservation": []} for i in range(AMR_SLOT_CAPACITY)}
        self.task = None
        self.task_id = None
        self.position = Position(x, y)
        self.goal = Position(x,y)
        self.goal_timestamp = None
        self.height = AMR_HEIGHT
        self.width = AMR_WIDTH
        self.color = AMR_COLOR

class Station:
    def __init__(self, station_id, x=0.0, y=0.0):
        self.id = station_id
        self.status = "idle"
        self.slots = {f"slot_{i}": {"object_id": None, "reservation": []} for i in range(STATION_SLOT_CAPACITY)}
        self.position = Position(x, y)
        # self.docking_position = Position()
        self.height = STATION_HEIGHT
        self.width = STATION_WIDTH
        self.color = STATION_COLOR
        self.margin = STATION_MARGIN

class Parking:
    def __init__(self, id, x=0.0, y=0.0):
        self.id = id
        self.occupied = False
        self.position = Position(x, y)
        self.height = PARKING_HEIGHT
        self.width = PARKING_WIDTH
        self.color = PARKING_COLOR
        self.margin = PARKING_MARGIN

class SubOrder:
    def __init__(self, suborder_id, order_id, sub_type, station_id, object_id, allow_grouping=True, priority=100):
        self.suborder_id = suborder_id
        self.order_id = order_id
        self.type = sub_type
        self.station_id = station_id
        self.object_id = object_id
        self.allow_grouping = allow_grouping
        self.priority = priority
        self.status = "pending" # pending, completed, failed
        self.task_id = None
        self.amr_slot = None
        self.station_slot = None
        self.timestep = 0
class Order:
    def __init__(self, order_id, source_station, destination_station, object_id, allow_grouping=True, priority=100):
        self.order_id = order_id
        self.object_id = object_id
        self.source_station = source_station
        self.destination_station = destination_station
        self.allow_grouping = allow_grouping
        self.priority = priority
        self.suborders = {"pickup": None, "delivery": None}
        self.status = "pending"
        self.assigned_amr = None

class Task:
    def __init__(self, task_id, assigned_amr, station):
        self.id = task_id
        self.assigned_amr = assigned_amr
        self.status = "queued"    # queued, executing, completed, failed
        self.station = station
        self.suborders = [] # [SubOrder]
        self.time_stamp = time.time()