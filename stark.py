import random
import numpy as np
import threading
import time
import copy
from configs import *
from classes import *
from functions import _distance, arrage_positions, promote_element
from flask_app import create_flask_app, run_flask
from pygame_renderer import Renderer
from typing import Union
from icecream import ic
from rich import print as rp

ic.configureOutput(includeContext=True)

class MedibotSystem:
    def __init__(self, render=False):
        self.reset()
        self.render_flag = render
        self.paused = False

    def reset(self):
        self.task_counter = 0
        self.order_counter = 0
        self.suboder_counter = 0
        self.tasks = {}
        self.orders = {}
        self.suborders = {}
        self.orders_history = {}
        self.suborders_history = {}
        self.tasks_history = {}
        self.amrs = {}
        self.amr_queues = {} # amr:{tasks:[Task,Task,Task,Task,Task,Task], expected_states: [{slot_n: "object_id"}}]*len
        self.station_queues = {} # station:{tasks:[Task,Task,Task,Task,Task,Task], expected_states: [{slot_n: "object_id"}}]*len}
        self.objects = {}
        self.stations = {}
        self.parkings = {}
        self.db_lock = threading.Lock()

        amr_positions = self.arrange_parking_positions(FLEET_SIZE)
        for i in range(FLEET_SIZE):
            amr_id = f"AMR{i}"
            self.register_entity(AMR, amr_id, amr_positions[i])
            parking_id = f"Parking{i}"
            self.parkings[amr_id] = Parking(parking_id, amr_positions[i].x, amr_positions[i].y)
            self.amrs[amr_id].parked = True

        station_positions = self.arrange_station_positions(TOTAL_STATIONS)
        for i in range(TOTAL_STATIONS):
            self.register_entity(Station, f"Station{i}", station_positions[i])

        available_locations = [(station_id, slot_id) for station_id, station in self.stations.items()
                                for slot_id, obj in station.slots.items() if obj["object_id"] is None]
        if len(available_locations) < OBJECTS:
            raise Exception("Not enough empty station slots to spawn all objects uniquely.")
        random.shuffle(available_locations)
        for i in range(OBJECTS):
            if i<9:
                object_id = f"Object0{i+1}"
            else:
                object_id = f"Object{i+1}"
            station_id, slot_id = available_locations[i]
            self.add_object(object_id, station_id, slot_id)
            rp(f"{object_id} spawned at {station_id} {slot_id}.")

    def register_entity(self, entity_class, entity_id:str, position:Position):
        if entity_class!=AMR and entity_class!=Station and entity_class!=Parking:
            raise Exception("Invalid entity class.")
        entity = entity_class(entity_id, position.x, position.y)
        if entity_class==AMR:
            self.amrs[entity_id] = entity
            self.amr_queues[entity_id] = {"tasks": [], "expected_states": []}
        elif entity_class==Station:
            self.stations[entity_id] = entity
        rp(f"{entity_id} registered at {position.x}, {position.y}.")
    
    def arrange_parking_positions(self, amr_count, spacing=50):
        positions = []
        y_positions = arrage_positions(amr_count, PARKING_HEIGHT, SCREEN_HEIGHT, spacing=spacing)
        for y in y_positions:
            positions.append(Position((SCREEN_WIDTH)//2, y))
        return positions

    def arrange_station_positions(self, station_capacity):
        left_positions = []
        right_positions = []

        left_y = arrage_positions(station_capacity // 2 + station_capacity % 2, STATION_HEIGHT, SCREEN_HEIGHT)
        right_y = arrage_positions(station_capacity // 2, STATION_HEIGHT, SCREEN_HEIGHT)

        for y in left_y:
            left_positions.append(Position(STATION_WIDTH//2, y))

        for y in right_y:
            right_positions.append(Position(SCREEN_WIDTH - STATION_WIDTH//2, y))

        return left_positions + right_positions

    def add_object(self, object_id, location:str, slot:str):
        self.objects[object_id] = (location, slot)
        if location in self.amrs.keys():
            self.amrs[location].slots[slot]["object_id"] = object_id
        elif location in self.stations.keys():
            self.stations[location].slots[slot]["object_id"] = object_id
        else:
            raise Exception("Invalid location")

    def add_order(self, object_id:str, source_station:str, destination_station:str, allow_grouping=True, priority=100):
        # Data validation
        success = False
        for station_id in [source_station, destination_station]:
            if station_id not in self.stations.keys():
                message = f"Invalid order: {object_id} is being processed by order {current_order_id}"
                rp(message)
                return {"message": message, "success": success}
            if not isinstance(self.stations[station_id], Station):
                message = f"Unexpected station type {type(self.stations[station_id])}"
                return {"message": message, "success": success}
        
        for current_order_id, current_order in self.orders.items():
            if not isinstance(current_order, Order):
                message = f"Unexpected order type {type(current_order)}"
                rp(message)
                return {"message": message, "success": success}
            if current_order.object_id == object_id:
                message = f"Invalid order: {object_id} is being processed by order {current_order_id}"
                rp(message)
                return {"message": message, "success": success}
        
        source_station = self.stations[source_station]
        destination_station = self.stations[destination_station]

        source_slots = source_station.slots.values()
        if not any([slot["object_id"] == object_id for slot in source_slots]):
            message = f"Invalid order: {object_id} not found in {source_station.id}"
            rp(message)
            return {"message": message, "success": success}

        with self.db_lock:
            self.order_counter += 1
            order_id = str(self.order_counter)
            self.orders[order_id] = Order(order_id=order_id, 
                                            object_id=object_id, 
                                            source_station=source_station, 
                                            destination_station=destination_station, 
                                            allow_grouping=allow_grouping, 
                                            priority=priority)
            new_order = self.orders[order_id]
            self.suboder_counter += 1
            source_suborder_id = str(self.suboder_counter)
            self.suborders[source_suborder_id] = SubOrder(suborder_id=source_suborder_id, 
                                                            order_id=order_id, 
                                                            sub_type="pickup", 
                                                            station_id=source_station.id, 
                                                            object_id=object_id, 
                                                            allow_grouping=allow_grouping, 
                                                            priority=priority)
            self.suboder_counter += 1
            destination_suborder_id = str(self.suboder_counter)
            self.suborders[destination_suborder_id] = SubOrder(suborder_id=destination_suborder_id, 
                                                                order_id=order_id, 
                                                                sub_type="delivery", 
                                                                station_id=destination_station.id, 
                                                                object_id=object_id, 
                                                                allow_grouping=allow_grouping, 
                                                                priority=priority)
            new_order.suborders["pickup"] = self.suborders[source_suborder_id]
            new_order.suborders["delivery"] = self.suborders[destination_suborder_id]
            
            success = True
            message = f"Order {order_id} created."
            rp(message)

            return {"message": message, "success": success, "order_id": order_id}
    
    def move_to_goal(self, amr_id, amr:AMR):
        for other_amr_id, other_amr in self.amrs.items():
            if not isinstance(other_amr, AMR):
                raise Exception("Unexpected amr type.")
            if amr_id == other_amr_id:
                continue
            if other_amr.goal == amr.goal and other_amr.goal_timestamp <= amr.goal_timestamp:
                rp(f"{other_amr_id} already at {other_amr.goal.x}, {other_amr.goal.y}, {amr_id} waiting.")
                return
        dx = amr.goal.x - amr.position.x
        dy = amr.goal.y - amr.position.y
        distance = np.hypot(dx, dy)
        if distance == 0:
            return  # Already at goal
        step = min(STEP_DISTANCE, distance)
        unit_vector = (dx / distance, dy / distance)
        amr.position.x += unit_vector[0] * step
        amr.position.y += unit_vector[1] * step

    def find_object_in_slots(self, device:Union[Station, AMR], object_id:str):
        return next((slot_id for slot_id, slot in device.slots.items() if slot["object_id"] == object_id), None)

    def find_available_slot(self, device:Union[Station, AMR]):
        return next((slot_id for slot_id, slot_object in device.slots.items() if slot_object["object_id"] is None), None)

    def get_reserved_slot(self, device:Union[Station, AMR], order_id):
        return next((slot_id for slot_id, slot_object in device.slots.items() if order_id in slot_object["reservation"]), None)

    def sort_alternating_suborders(self, task_id):
        task = self.tasks[task_id]
        amr_id = task.assigned_amr
        station = task.station
        pickups = [s for s in task.suborders if s.type == "pickup" and s.status == "pending"]
        deliveries = [s for s in task.suborders if s.type == "delivery" and s.status == "pending"]
        station_available = sum(1 for s in station.slots.values() if s["object_id"] is None)
        amr_available = sum(1 for s in self.amrs[amr_id].slots.values() if s["object_id"] is None)
        ic(station_available, amr_available)
        new_order = []
        if station_available < amr_available:
            while pickups or deliveries:
                if pickups:
                    new_order.append(pickups.pop(0))
                if deliveries:
                    new_order.append(deliveries.pop(0))
        else:
            while pickups or deliveries:
                if deliveries:
                    new_order.append(deliveries.pop(0))
                if pickups:
                    new_order.append(pickups.pop(0))

        task.suborders = new_order

    def rearrange_suborders(self, task_id, amr_id):
        task = self.tasks[task_id]
        station = task.station
        suborders = task.suborders
        pending_pickups = [s for s in suborders if s.type == "pickup" and s.status == "pending"]
        pending_deliveries = [s for s in suborders if s.type == "delivery" and s.status == "pending"]
        station_available = sum(1 for s in station.slots.values() if s["object_id"] is None)
        amr_available = sum(1 for s in self.amrs[amr_id].slots.values() if s["object_id"] is None)

        # Deadlock condition: both full
        if station_available == 0 and amr_available == 0:
            rp(amr_id, station.id, suborders)
            raise Exception("Deadlock: Station and AMR are full.")
        # Station full: must prioritize pickup to free space
        if station_available == 0 and amr_available > 0:
            rp("Station full. Prioritizing pickup.")
            if pending_pickups:
                promote_element(pending_pickups[0], suborders)
                rp(f"Suborder {pending_pickups[0].suborder_id} is promoted.")
            else:
                raise Exception("Deadlock: No pickup available to free station slot.")
        # AMR full: must prioritize delivery to free space
        elif amr_available == 0 and station_available > 0:
            rp("AMR full. Prioritizing delivery.")
            if pending_deliveries:
                promote_element(pending_deliveries[0], suborders)
                rp(f"Suborder {pending_deliveries[0].suborder_id} is promoted.")
            else:
                raise Exception("Deadlock: No delivery available to free AMR slot.")

        # Both have space: alternate pickup/delivery (optional fallback behavior)
        else:
            # Optional: alternate if desired, but keep simple
            if pending_deliveries and pending_pickups:
                # Alternate starting from pickup
                if len(pending_pickups) >= len(pending_deliveries):
                    promote_element(pending_pickups[0], suborders)
                    rp(f"Suborder {pending_pickups[0].suborder_id} is promoted.")
                else:
                    promote_element(pending_deliveries[0], suborders)
                    rp(f"Suborder {pending_deliveries[0].suborder_id} is promoted.")
        ic([suborder.suborder_id for suborder in self.tasks[task_id].suborders])

    def suborder_execution(self, amr_id, amr:AMR):
        if not isinstance(amr, AMR):
            raise Exception("Unexpected amr type.")
        
        # Obtain the first uncompleted suborder
        for suborder in self.tasks[amr.task_id].suborders:
            if not isinstance(suborder, SubOrder):
                raise Exception("Unexpected suborder type.")
            if suborder.status in ["completed", "failed"]:
                continue
            break
        suborder_id = suborder.suborder_id
        station = self.stations[suborder.station_id]
        order_id = self.suborders[suborder_id].order_id
        
        if suborder.status == "pending":
            rp("Rearranging suborders")
            self.rearrange_suborders(amr.task_id, amr_id)
            rp(f"Executing suborder {suborder_id} for {amr_id}")
            suborder.status = "executing"
            if suborder.type == "pickup":
                rp(f"Suborder is to pickup {suborder.object_id} from {suborder.station_id}")
                suborder.station_slot = self.find_object_in_slots(station, suborder.object_id)
                suborder.amr_slot = self.find_available_slot(amr)
                
                if not suborder.station_slot or not suborder.amr_slot:
                    rp(amr.slots)
                    rp(station.slots)
                    rp(f"Reserved slot for order {order_id} not found in AMR.") if not suborder.station_slot  else None
                    rp(f"Object {suborder.object_id} not found in station {suborder.station_id}") if not suborder.amr_slot else None
                    suborder.status = "failed"
                    amr.status = "error"
                    return
                
            elif suborder.type == "delivery":
                rp(f"Suborder is to deliver {suborder.object_id} to {suborder.station_id}")
                suborder.amr_slot = self.find_object_in_slots(self.amrs[amr_id], suborder.object_id)
                suborder.station_slot = self.get_reserved_slot(station, order_id)
                if not suborder.station_slot or not suborder.amr_slot:
                    rp(f"Reserved slot for order {order_id} not found in station.") if not suborder.station_slot else None
                    rp(f"Object {suborder.object_id} not found in AMR {amr_id}") if not suborder.amr_slot else None
                    suborder.status = "failed"
                    amr.status = "error"
                    return
            else:
                raise Exception("Invalid suborder type.")
        
        elif suborder.status == "executing":
            if suborder.timestep >= SUBORDER_DURATION:
                if suborder.type == "pickup":
                    amr.slots[suborder.amr_slot]["object_id"] = suborder.object_id
                    station.slots[suborder.station_slot]["object_id"] = None
                    station.slots[suborder.station_slot]["reservation"].remove(order_id)
                    rp(f"Transferred {suborder.object_id} from {suborder.station_id} {suborder.station_slot} to {amr_id} {suborder.station_slot}")
                elif suborder.type == "delivery":
                    station.slots[suborder.station_slot]["object_id"] = suborder.object_id
                    station.slots[suborder.station_slot]["reservation"].remove(order_id)
                    amr.slots[suborder.amr_slot]["object_id"] = None
                    rp(f"Transferred {suborder.object_id} from {amr_id} {suborder.amr_slot} to {suborder.station_id} {suborder.station_slot}")
                self.suborders[suborder_id].status = "completed"
            else:
                suborder.timestep += 1
        return

    def cost_based_assignment(self, order:Order):
        cost_dict = {amr_id: {"cost": 0, "pickup_index": None, "delivery_index": None} for amr_id in self.amrs.keys()}
        rp(self.amr_queues)

        # Check possibilities
        for amr_id, queue in self.amr_queues.items():
            for task_index, task in enumerate(queue["tasks"]):
                if not isinstance(task, Task):
                    raise Exception("Unexpected task type.")
                if task.status in ["completed", "failed"]:
                    continue
                if task.station != order.source_station:
                    continue
                # verify if this task can handle extra pickup
                rp(queue["expected_states"], task_index)
                
                object_count = len(queue["expected_states"][task_index])
                ic(object_count)
                if object_count < AMR_SLOT_CAPACITY:
                    rp(f"pickup suborder of order {order.order_id} can be assigned to queue{task_index} of {amr_id}")
                    cost_dict[amr_id]["pickup_index"] = task_index
                    rp(cost_dict[amr_id])
                    break

            if cost_dict[amr_id]["pickup_index"] != None:
                # found task to inject pickup
                for task in queue["tasks"][cost_dict[amr_id]["pickup_index"]:]: # start from index after pickup task
                    task_index = queue["tasks"].index(task)
                    ic(task_index)
                    if not isinstance(task, Task):
                        raise Exception("Unexpected task type.")
                    ic(task.station.id, order.destination_station.id)
                    if task.station != order.destination_station:
                        continue
                    # verify if this task can handle extra delivery
                    rp(f"delivery suborder of order {order.order_id} can be assigned to queue{task_index} of {amr_id}")
                    cost_dict[amr_id]["delivery_index"] = task_index
                    break
                if cost_dict[amr_id]["delivery_index"] != None:
                    continue

            pickup_queue_index = cost_dict[amr_id]["pickup_index"]
            delivery_queue_index = cost_dict[amr_id]["delivery_index"]
            amr_cost = cost_dict[amr_id]["cost"]
            # Cost calculation here
            if len(queue["tasks"]) != 0:
                # add the first station distance cost
                amr_cost += _distance(self.amrs[amr_id].position, queue["tasks"][0].station.position) * DISTANCE_COST
                amr_cost += len(queue["tasks"][0].suborders) * TRANSFER_COST
            else:
                amr_cost += _distance(self.amrs[amr_id].position, order.source_station.position) * DISTANCE_COST
            
            if pickup_queue_index != None and delivery_queue_index != None:
                for task in queue["tasks"][1:delivery_queue_index]:
                    task_index = queue["tasks"].index(task)
                    amr_cost += _distance(task.station.position, queue["tasks"][task_index-1].station.position) * DISTANCE_COST
                    amr_cost += len(task.suborders) * TRANSFER_COST
            elif pickup_queue_index != None and delivery_queue_index == None:
                # create one new task for delivery
                for task in queue["tasks"][1:]: # all cost towards end of queue
                    task_index = queue["tasks"].index(task)
                    amr_cost += _distance(task.station.position, queue["tasks"][task_index-1].station.position) * DISTANCE_COST
                    amr_cost += len(task.suborders) * TRANSFER_COST
                # cost of last task to new delivery station
                cost_dict[amr_id]["cost"] += _distance(queue["tasks"][-1].station.position, order.destination_station.position) * DISTANCE_COST
            elif pickup_queue_index == None and delivery_queue_index == None:
                # create one new task for pickup and one new task for delivery
                if len(queue["tasks"]) != 0:
                    for i, task in enumerate(queue["tasks"][1:]): # all cost towards end of queue
                        amr_cost += _distance(task.station.position, queue["tasks"][i-1].station.position) * DISTANCE_COST
                        amr_cost += len(task.suborders) * TRANSFER_COST
                    rp(queue["tasks"][-1].station, order.source_station)
                    amr_cost += _distance(queue["tasks"][-1].station.position, order.source_station.position) * DISTANCE_COST
            else:
                rp("Invalid scenario in cost calculation, pickup index is None but delivery index is not.")
        costs = {amr_id: cost_dict[amr_id]["cost"] for amr_id in cost_dict.keys()}
        rp(costs)

        # Actual assigning and expected states
        best_amr_id = min(cost_dict, key=lambda amr_id: cost_dict[amr_id]["cost"])
        order.assigned_amr = best_amr_id
        pickup_queue_index = cost_dict[best_amr_id]["pickup_index"]
        delivery_queue_index = cost_dict[best_amr_id]["delivery_index"]
        queue = self.amr_queues[best_amr_id]
        source_station_id = order.source_station.id
        destination_station_id = order.destination_station.id
        expected_states = queue["expected_states"]

        if pickup_queue_index != None:
            pickup_task_id = queue["tasks"][pickup_queue_index].id
            order.suborders["pickup"].task_id = pickup_task_id
            rp(self.suborders[order.suborders["pickup"].suborder_id].task_id)
            self.tasks[pickup_task_id].suborders.append(order.suborders["pickup"])
            self.sort_alternating_suborders(pickup_task_id)
            ic([suborder.suborder_id for suborder in self.tasks[pickup_task_id].suborders])
        else:
            self.task_counter += 1
            pickup_task_id = str(self.task_counter)
            self.tasks[pickup_task_id] = Task(task_id=pickup_task_id, assigned_amr=best_amr_id, station=self.stations[source_station_id])
            self.suborders[order.suborders["pickup"].suborder_id].task_id = pickup_task_id
            order.suborders["pickup"] = self.suborders[order.suborders["pickup"].suborder_id]
            self.tasks[pickup_task_id].suborders.append(order.suborders["pickup"])
            queue["tasks"].append(self.tasks[pickup_task_id])
            pickup_queue_index = len(queue["tasks"])-1

            # Assuming add task to end of queue, modify for expected states if insert prioritized task within queue
            expected_states.append(set() if len(expected_states)==0 else copy.copy(expected_states[-1]))

        if delivery_queue_index != None:
            delivery_task_id = queue["tasks"][cost_dict[best_amr_id]["delivery_index"]].id
            self.tasks[delivery_task_id].suborders.append(order.suborders["delivery"])
            self.suborders[order.suborders["delivery"].suborder_id].task_id = delivery_task_id
            rp(self.suborders[order.suborders["delivery"].suborder_id].task_id)
            self.sort_alternating_suborders(pickup_task_id)
            ic([suborder.suborder_id for suborder in self.tasks[pickup_task_id].suborders])
        else:
            self.task_counter += 1
            delivery_task_id = str(self.task_counter)
            self.tasks[delivery_task_id] = Task(task_id=delivery_task_id, assigned_amr=best_amr_id, station=self.stations[destination_station_id])
            self.suborders[order.suborders["delivery"].suborder_id].task_id = delivery_task_id
            order.suborders["delivery"] = self.suborders[order.suborders["delivery"].suborder_id]
            self.tasks[delivery_task_id].suborders.append(order.suborders["delivery"])
            queue["tasks"].append(self.tasks[delivery_task_id])
            delivery_queue_index = len(queue["tasks"])-1

            # Assuming add task to end of queue, modify for expected states if insert prioritized task within queue
            expected_states.append(copy.copy(expected_states[-1])) # also append for delivery states

        for state in expected_states[pickup_queue_index:delivery_queue_index]:
            state.add(order.object_id)

    def amr_slot_reservation(self, amr: AMR):
        pickup_suborders = len([s for s in amr.task.suborders if s.type == "pickup" and s.status == "pending"])
        delivery_suborders = len([s for s in amr.task.suborders if s.type == "delivery" and s.status == "pending"])
        available_slots = len([slot for slot in amr.slots.values() if slot["object_id"] is None])
        required_slots = max(0, pickup_suborders - delivery_suborders)
        rp(f"{amr.id} has {available_slots} available_slots, pickup suborders: {pickup_suborders}, delivery suborders: {delivery_suborders}, required reservations: {required_slots}")

        if available_slots < required_slots:
            raise Exception("Not enough available slots for pickup and delivery suborders of current task.")
        
    def station_slot_reservation(self, amr: AMR):
        station = self.stations[amr.task.station.id]
        suborders = [s for s in amr.task.suborders if s.status == "pending"]

        # Start with real available slots (empty and not reserved)
        real_available_slots = [
            slot_id for slot_id, slot in station.slots.items()
            if slot["object_id"] is None and (not slot.get("reservation") or len(slot["reservation"]) == 0)
        ]
        available_slot_queue = real_available_slots.copy()
        simulated_available = len(real_available_slots)
        for suborder in suborders:
            if suborder.type == "pickup":
                # Reserve the slot where the object is
                for slot_id, slot in station.slots.items():
                    if slot["object_id"] != suborder.object_id:
                        continue
                    if suborder.order_id not in slot["reservation"]:
                        slot["reservation"].append(suborder.order_id)
                        rp(f"{amr.id} reserved {station.id} {slot_id} for order {suborder.order_id} (pickup)")
                    # After pickup, this slot will become free
                    simulated_available += 1
                    available_slot_queue.append(slot_id)  # Now reusable
                    break

            elif suborder.type == "delivery":
                if simulated_available <= 0:
                    raise Exception("Not enough effective station slots to schedule delivery suborders in task.")
                simulated_available -= 1
                if not available_slot_queue:
                    raise Exception("Logic error: simulated_available mismatch real available slots.")
                slot_id = available_slot_queue.pop(0)
                slot = station.slots[slot_id]
                if suborder.order_id not in slot["reservation"]:
                    slot["reservation"].append(suborder.order_id)
                    rp(f"{amr.id} reserved {station.id} {slot_id} for order {suborder.order_id} (delivery)")

    def amr_state_validation(self, amr:AMR):
        actual_objects = {slot["object_id"] for slot in amr.slots.values() if slot["object_id"] is not None}
        actual_nones = sum(1 for slot in amr.slots.values() if slot["object_id"] is None)
        expected_objects = self.amr_queues[amr.id]["expected_states"][0]
        expected_nones = AMR_SLOT_CAPACITY - len(expected_objects)
        if actual_objects != expected_objects:
            raise Exception(f"Object mismatch. Expected: {expected_objects}, Got: {actual_objects}")
        if actual_nones != expected_nones:
            raise Exception(f"Empty slot mismatch. Expected {expected_nones} empty slots, got {actual_nones}")
        print("AMR state is valid: Correct objects and correct number of empty slots.")

    def pre_task_validation(self, amr:AMR, task:Task):
        has_valid_suborder = False
        queue = self.amr_queues[amr.id]

        if len(queue["tasks"]) == 0:
            print(f"AMR has no task queue")
            return
        station = task.station
        if not isinstance(station, Station):
            raise Exception("Unexpected station type.")
        if station.status != "idle":
            print(f"Station is not idle")
            return

        suborders = task.suborders
        original_suborders = suborders.copy()
        pickup_suborders = [s for s in suborders if s.type == "pickup"]
        delivery_suborders = [s for s in suborders if s.type == "delivery"]
        station_objects = {slot["object_id"] for slot in station.slots.values() if slot["object_id"] is not None}
        station_real_available_slots = len([slot_id for slot_id, slot in station.slots.items() if slot["object_id"] is None])
        amr_objects = {slot["object_id"] for slot in amr.slots.values() if slot["object_id"] is not None}
        amr_real_available_slots = len([slot_id for slot_id, slot in amr.slots.items() if slot["object_id"] is None])
        invalid_pickup_suborders = {s for s in pickup_suborders if s.object_id not in station_objects}
        invalid_delivery_suborders = {s for s in delivery_suborders if s.object_id not in amr_objects}
        
        for invalid_pickup in invalid_pickup_suborders:
            invalid_pickup.status = "failed"
            print(f"Cant pickup object {invalid_pickup.object_id} from station {station.id}")
        for invalid_delivery in invalid_delivery_suborders:
            invalid_delivery.status = "failed"
            print(f"Cant deliver object {invalid_delivery.object_id} to station {station.id}")

        suborders = list(set(suborders) - invalid_pickup_suborders - invalid_delivery_suborders)
        if len(suborders) == 0:
            return has_valid_suborder

        pickup_suborders = [s for s in suborders if s.type == "pickup"]
        delivery_suborders = [s for s in suborders if s.type == "delivery"]

        delayed_pickup = []
        delayed_delivery = []
        station_required_slots = max(0, len(delivery_suborders) - len(pickup_suborders))
        amr_required_slots = max(0, len(pickup_suborders) - len(delivery_suborders))
        if station_real_available_slots < station_required_slots:
            n_delivery_to_remove = station_required_slots - station_real_available_slots
            if len(delivery_suborders) == n_delivery_to_remove:
                delayed_delivery = delivery_suborders.copy()
                delivery_suborders = []
            else:
                delivery_suborders = delivery_suborders[:len(delivery_suborders)-n_delivery_to_remove]
                delayed_delivery = delivery_suborders[:n_delivery_to_remove]
        if amr_real_available_slots < amr_required_slots:
            n_order_to_remove = amr_required_slots - amr_real_available_slots
            pickup_suborders = pickup_suborders[n_order_to_remove:]
            delayed_pickup = pickup_suborders[:n_order_to_remove]

        task.suborders = pickup_suborders + delivery_suborders
        if len(task.suborders) != 0:
            task.status = "queued"
            has_valid_suborder = True
        print(f"Task {task.id} has {'no ' if not has_valid_suborder else ''}valid suborders")

        if delayed_pickup:
            for suborder in delayed_pickup:
                order = self.orders[suborder.order_id]
                order.suborders["pickup"].task_id = None
                order.suborders["delivery"].task_id = None
        if delayed_delivery:
            for suborder in delayed_delivery:
                print(f"Delayed {suborder.object_id} delivery to station {suborder.station_id}")
        if set(original_suborders) == set(delayed_delivery):
            print("putting task to sleep")
            task.status = "sleep"
            task.suborders = delayed_delivery
        
        self.update_expected_states(amr) if any(delayed_pickup) or any(delayed_delivery) else None
        return has_valid_suborder


    def update_expected_states(self, amr:AMR):
        queue = self.amr_queues[amr.id]
        amr_current_objects = {slot["object_id"] for slot in amr.slots.values() if slot["object_id"] is not None}
        for task_index, task in enumerate(queue["tasks"]):
            expected_states = queue["expected_states"]
            expected_states[task_index] = amr_current_objects.copy() if task_index == 0 else expected_states[task_index-1].copy()
            pickup_objects = {suborder.object_id for suborder in task.suborders if suborder.type == "pickup"}
            delivery_objects = {suborder.object_id for suborder in task.suborders if suborder.type == "delivery"}
            expected_states[task_index] = expected_states[task_index].union(pickup_objects)
            expected_states[task_index] = expected_states[task_index].difference(delivery_objects)
        rp(f"{amr.id} task queue: {[task.id for task in queue['tasks']]}")
        rp(f"{amr.id} expected states: {queue['expected_states']}")

    def order_validation(self):
        pass

    def rearrange_amr_queue(self, amr:AMR):
        # check if all task has any valid delivery
        # if totally no valid task to do, sleep and no rearrange
        # if have valid task, do it and delay invalid
        if len(self.amr_queues[amr.id]["tasks"]) == 0:
            return
        for queue_index, task in enumerate(self.amr_queues[amr.id]["tasks"]):
            if not isinstance(task, Task):
                raise Exception("Unexpected task type.")
            has_valid_suborder = self.pre_task_validation(self.amrs[amr.id], task)
            ic(has_valid_suborder)
            # if not has_valid_suborder:
            #     self.amr_queues[amr.id]["tasks"].append(self.amr_queues[amr.id]["tasks"].pop(0))
            if has_valid_suborder:
                task.station.status = "busy"
                self.sort_alternating_suborders(task.id)
                amr.status = "busy"
                amr.task = task
                amr.task_id = task.id
                amr.goal_timestamp = time.time()
                amr.goal = task.station.position
                task.status = "executing"
                self.amr_slot_reservation(amr)
                self.station_slot_reservation(amr)
                rp(f"{amr.id} is moving to task goal")
                break
        
        if not has_valid_suborder:
            print(f"All suborders in task in {amr.id} queue are invalid")
            ic(self.amr_queues[amr.id]["tasks"][0].suborders)
            ic(self.amr_queues[amr.id])
        if self.amr_queues[amr.id]["tasks"][0].status == "sleep":
            print(f"first task in {amr.id} queue is sleep, putting to last")
            self.amr_queues[amr.id]["tasks"].append(self.amr_queues[amr.id]["tasks"].pop(0))
            self.update_expected_states(amr)

    def step(self):
        if not self.paused:
            for amr_id, amr in self.amrs.items():
                if not isinstance(amr, AMR):
                    raise Exception("Unexpected amr type.")
                queue = self.amr_queues[amr_id]
                if len(queue["tasks"]) == 0 and amr.is_parked:
                    continue
                # ic(amr.status)
                if amr.status == "busy" and amr.task_id is not None:
                    if not np.allclose([amr.position.x, amr.position.y], [amr.goal.x, amr.goal.y], atol=0.01):
                        self.move_to_goal(amr_id, amr)
                        amr.is_moving = True
                        amr.is_parked = False
                        continue
                    else:
                        rp(f"{amr.id} arrived at goal") if amr.is_moving else None
                        amr.is_moving = False
                        if all([suborder.status=="completed" for suborder in self.tasks[amr.task_id].suborders]):
                            self.amr_state_validation(amr)
                            self.tasks[amr.task_id].status = "completed"
                            amr.status = "idle"
                            amr.task_id = None
                            continue
                        self.suborder_execution(amr_id, amr)
                        continue
                if amr.status == "idle":
                    if sum(1 for task in queue["tasks"] if task.status =="queued") == 0:
                        # no more task for this amr
                        amr.goal = self.parkings[amr_id].position
                        if not np.allclose([amr.position.x, amr.position.y], [amr.goal.x, amr.goal.y], atol=0.01):
                            rp(f"{amr_id} is moving to parking") if not amr.is_moving else None
                            self.move_to_goal(amr_id, amr)
                            amr.is_moving = True
                        else:
                            rp(f"{amr_id} arrived parking") if amr.is_moving else None
                            amr.is_moving = False
                            amr.is_parked = True
                        continue
                    task = queue["tasks"][0]
                    task_id = task.id
                    if not isinstance(task, Task):
                        raise Exception("Unexpected task type.")
                    if task.status == "completed":
                        rp(f"Task {task_id} completed")
                        task.station.status = "idle"
                        self.tasks_history[task_id] = task
                        self.tasks.pop(task_id)
                        queue["tasks"].pop(0)
                        queue["expected_states"].pop(0)
                        ic(queue)
                        continue
                    if task.status == "failed":
                        rp(f"Task {task_id} failed, waiting for user to cancel")
                        continue
                    if task.status == "queued" or task.status == "sleep":
                        self.rearrange_amr_queue(amr)
                        continue

        completed_orders = []
        with self.db_lock:
            for order_id, order in self.orders.items():
                if not isinstance(order, Order):
                    raise Exception("Unexpected order type.")
                if order.status == "pending": # not fulfilled
                    if all([suborder.status=="completed" for suborder in order.suborders.values()]):
                        self.orders_history[order_id] = order
                        for suborder in order.suborders.values():
                            self.suborders_history[suborder.suborder_id] = suborder
                            self.suborders.pop(suborder.suborder_id)
                        order.status = "completed"
                        rp(f"Order {order_id} {order.status}.")
                        completed_orders.append(order_id)
                        continue
                    if any([suborder.status=="failed" for suborder in order.suborders.values()]):
                        order.status = "failed"
                        rp(f"Order {order_id} {order.status}.")
                        continue
                    
                    pickup_pending = order.suborders["pickup"].status == "pending" and order.suborders["pickup"].task_id is None
                    if pickup_pending:
                        order.assigned_amr = None
                        order.suborders["delivery"].status = "pending"
                        order.suborders["delivery"].task_id = None
                        self.order_validation()
                        self.cost_based_assignment(order)
                        self.update_expected_states(self.amrs[order.assigned_amr])

                        # loop for all queue task for same station and merge suborder
            for order_id in completed_orders:
                self.orders.pop(order_id)

if __name__ == "__main__":
    medibot_system = MedibotSystem(render=True)
    renderer = Renderer(medibot_system) if medibot_system.render_flag else None
    app = create_flask_app(medibot_system)
    flask_thread = threading.Thread(target=run_flask, args=(app,), daemon=True)
    flask_thread.start()
    while True:
        start = time.time()
        medibot_system.step()
        renderer.render() if medibot_system.render_flag else None
        renderer.handle_events() if medibot_system.render_flag else None
        time.sleep(max(0, 0.01 - (time.time() - start)))  # Maintain 10Hz
        # rp(f"Time taken per step: {time.time() - start:.5f} seconds")
