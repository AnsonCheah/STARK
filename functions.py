from classes import Position, Task
import numpy as np

def _distance(pos1:Position, pos2:Position):
    return np.linalg.norm(np.array([pos1.x, pos1.y]) - np.array([pos2.x, pos2.y]))

def arrage_positions(count, entity_size, axis_max, spacing=50):
    total_height = count * entity_size + (count - 1) * spacing if count > 0 else 0
    start = (axis_max - total_height + entity_size) // 2
    return [start + i * (entity_size + spacing) for i in range(count)]

def promote_element(element, lst):
    try:
        lst.remove(element)
        lst.insert(0, element)
    except ValueError:
        pass

# def effective_slot(task:Task):
#     suborders = task.suborders
#     pickup_suborders = [s for s in suborders if s.type == "pickup"]
#     delivery_suborders = [s for s in suborders if s.type == "delivery"]
#     station_required_slots = max(0, len(delivery_suborders) - len(pickup_suborders))
#     amr_required_slots = max(0, len(pickup_suborders) - len(delivery_suborders))
#     return station_required_slots, amr_required_slots