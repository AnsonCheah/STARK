from flask import Flask, request, jsonify
from classes import *

def create_flask_app(system):
    app = Flask(__name__)

    @app.route("/medibot/add_order", methods=["POST"])
    def add_order():
        print("received request to add order")
        try:
            data = request.json
                
            source_station = data.get("source_station")
            destination_station = data.get("destination_station")
            allow_grouping = data.get("allow_grouping", True)
            priority = data.get("priority", 100)
            object_id = data.get("object_id")
            if type(object_id) == str:
                object_id = [object_id]
            res = []
            if type(object_id) == list and len(object_id) > 0 and all(isinstance(item, str) for item in object_id):
                for item in object_id:
                    res.append(system.add_order(item, source_station, destination_station,
                                            allow_grouping=allow_grouping, priority=priority))

            return jsonify(res)
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
        
    @app.route("/medibot/orders", methods=["GET"])
    def get_orders():
        try:
            res = {}
            for order_id, order in system.orders.items():
                if not isinstance(order, Order):
                    raise Exception("Unexpected order type.")
                res[order_id] = {
                    "id": order.order_id, 
                    "object_id": order.object_id, 
                    "source_station": order.source_station.id, 
                    "destination_station": order.destination_station.id,
                    "status": order.status, 
                    "pickup_id": order.suborders["pickup"].suborder_id, 
                    "delivery_id": order.suborders["pickup"].suborder_id, 
                    "allow_grouping": order.allow_grouping, 
                    "priority": order.priority
                    }
            return jsonify({"status": "success", "orders": res})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
        
    @app.route("/medibot/suborders", methods=["GET"])
    def get_suborders():
        try:
            res = {}
            for suborder_id, suborder in system.suborders.items():
                if not isinstance(suborder, SubOrder):
                    raise Exception("Unexpected suborder type.")
                res[suborder_id] = {
                    "id": suborder.suborder_id,
                    "order_id": suborder.order_id,
                    "type": suborder.type,
                    "station_id": suborder.station_id,
                    "object_id": suborder.object_id,
                    "status": suborder.status,
                    "allow_grouping": suborder.allow_grouping,
                    "priority": suborder.priority
                }
            return jsonify({"status": "success", "suborders": res})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
        
    @app.route("/medibot/tasks", methods=["GET"])
    def get_tasks():
        try:
            res = {}
            for task_id, task in system.tasks.items():
                if not isinstance(task, Task):
                    raise Exception("Unexpected task type.")
                suborder_description = []
                for suborder in task.suborders:
                    suborder_description.append(f"{suborder.suborder_id}: {suborder.type} {suborder.object_id} {'to' if suborder.type == 'delivery' else 'from'} {suborder.station_id}")
                res[task_id] = {
                    "id": task.id,
                    "assigned_amr": task.assigned_amr,
                    "status": task.status,
                    "station": task.station.id,
                    "suborders": [suborder.suborder_id for suborder in task.suborders],
                    "suborder_description": suborder_description
                }
            return jsonify({"status": "success", "tasks": res})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})

    @app.route("/medibot/queues", methods=["GET"])
    def get_queue():
        try:
            tasks = []
            expected_states = []
            amr_id = request.args.get("amr_id")
            for state in system.amr_queues[amr_id]["expected_states"]:
                expected_states.append(list(state))
            for task in system.amr_queues[amr_id]["tasks"]:
                if not isinstance(task, Task):
                    raise Exception("Unexpected task type.")
                suborder_description = []
                for suborder in task.suborders:
                    suborder_description.append(f"{suborder.suborder_id}: {suborder.type} {suborder.object_id} {'to' if suborder.type == 'delivery' else 'from'} {suborder.station_id}")
                tasks.append({
                    "id": task.id,
                    "assigned_amr": task.assigned_amr,
                    "status": task.status,
                    "station": task.station.id,
                    "suborders": [suborder.suborder_id for suborder in task.suborders],
                    "suborder_description": suborder_description
                })

            return jsonify({"status": "success", "tasks": tasks, "expected_states": expected_states})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})


    @app.route("/medibot/reset", methods=["POST"])
    def reset():
        try:
            system.reset()
            return jsonify({"status": "success"})
        except:
            return jsonify({"status": "error"})

    return app

    

def run_flask(app):
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)  # use_reloader=False prevents double-threading issues
    print("Flask is running in a background thread.")
    
