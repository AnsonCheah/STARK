from classes import Position
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