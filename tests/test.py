from src.queues_dir import QueuesDirectory
from src.config import *
from access_control_block import AccessControlBlock
from resource_manager import ResourceManager
from queue import Empty
from src.mission_planner import MissionPlanner
import time
from src.safety_block import BaseSafetyBlock
from src.control_system import BaseControlSystem


def test_access_control_allowed():
    """
    Проверяем, что при sender_id="alice", route_id="route_1" (если разрешено)
    в очередь RESOURCE_MANAGER_QUEUE_NAME попадёт нужный Event.
    """
    queues_dir = QueuesDirectory()
    allowed_mapping = {
        "alice": ["route_1", "route_2"],
        "bob": ["route_3"]
    }
    acb = AccessControlBlock(queues_dir, allowed_mapping)
    res_mng = ResourceManager(queues_dir, {})

    # 7.1) Запрос, который должен пройти
    acb._process_access_request(sender_id="alice", route_id="route_1")

    # 7.2) Проверяем содержимое очереди ResourceManager
    q_rm = queues_dir.get_queue(RESOURCE_MANAGER_QUEUE_NAME)
    try:
        ev = q_rm.get(timeout=0.1)
    except Empty:
        raise AssertionError("Ожидали Event в очереди ResourceManager, но она пуста!")

    assert ev.source == ACCESS_CONTROL_QUEUE_NAME
    assert ev.destination == RESOURCE_MANAGER_QUEUE_NAME
    assert ev.operation == "take_mission"
    assert ev.parameters == {"sender_id": "alice", "route_id": "route_1"}
    print("✅ test_access_control_allowed прошёл успешно.")


def test_access_control_denied():
    """
    Проверяем, что при отсутствии разрешения (например, alice не имеет route_3),
    ничего не кладётся в очередь ResourceManager.
    """
    queues_dir = QueuesDirectory()
    allowed_mapping = {"alice": ["route_1", "route_2"]}
    acb = AccessControlBlock(queues_dir, allowed_mapping)
    _ = MissionPlanner(queues_dir)
    _ = ResourceManager(queues_dir, {})
    time.sleep(0.01)

    # 7.1) Запрос, который НЕ должен пройти
    acb._process_access_request(sender_id="alice", route_id="route_3")

    # 7.2) Проверяем, что очередь пуста
    q_rm = queues_dir.get_queue(RESOURCE_MANAGER_QUEUE_NAME)
    assert q_rm.empty(), "Ожидали пустую очередь ResourceManager, но там что-то есть!"
    print("✅ test_access_control_denied прошёл успешно.")


def test_access_control_bad_params():
    """
    Проверяем, что при sender_id="" или route_id=None ничего не кладётся.
    """
    queues_dir = QueuesDirectory()
    allowed_mapping = {"alice": ["route_1"]}
    acb = AccessControlBlock(queues_dir, allowed_mapping)
    _ = ResourceManager(queues_dir, {})
    time.sleep(0.01)

    acb._process_access_request(sender_id="", route_id="route_1")
    acb._process_access_request(sender_id="alice", route_id=None)

    q_rm = queues_dir.get_queue(RESOURCE_MANAGER_QUEUE_NAME)
    assert q_rm.empty(), "Ожидали, что при некорректных параметрах очередь пустая!"
    print("✅ test_access_control_bad_params прошёл успешно.")


def test_resource_manager_dispatch():
    """
    Проверяем, что при успешном получении mission_data
    ResourceManager кладёт два нужных Event-а: в CONTROL_SYSTEM и SAFETY_BLOCK.
    """
    queues_dir = QueuesDirectory()
    # routes_storage лишь для полноты картины; _dispatch_mission работает «просто с mission_data»
    routes_storage = {
        "route_1": {"home": (0, 0), "waypoints": [(1, 1), (2, 2)], "speed_limits": [10, 20], "armed": False}
    }
    rm = ResourceManager(queues_dir, routes_storage)
    _ = BaseSafetyBlock(queues_dir)
    _ = BaseControlSystem(queues_dir)
    time.sleep(0.01)

    # Вызываем «диспатч» напрямую
    rm._dispatch_mission(route_data=routes_storage["route_1"])
    time.sleep(0.01)

    # Проверяем очередь CONTROL_SYSTEM
    qc = queues_dir.get_queue(CONTROL_SYSTEM_QUEUE_NAME)
    assert not qc.empty(), "Ожидали Event в CONTROL_SYSTEM, но очередь пуста!"
    ev_c = qc.get_nowait()
    assert ev_c.operation == "set_mission"

    # Проверяем очередь SAFETY_BLOCK
    qs = queues_dir.get_queue(SAFETY_BLOCK_QUEUE_NAME)
    assert not qs.empty(), "Ожидали Event в SAFETY_BLOCK, но очередь пуста!"
    ev_s = qs.get_nowait()
    assert ev_s.operation == "set_mission"

    print("✅ test_resource_manager_dispatch прошёл успешно.")


def test_resource_manager_rejection():
    """
    Проверяем, что при вызове _send_rejection формируется нужный Event
    в очередь PLANNER.
    """
    queues_dir = QueuesDirectory()
    routes_storage = {}  # пусто
    rm = ResourceManager(queues_dir, routes_storage)
    _ = MissionPlanner(queues_dir)
    time.sleep(0.01)

    # Вызываем «отказ»
    rm._send_rejection(sender_id="alice", route_id="route_9", reason="not_found")
    time.sleep(0.01)

    qp = queues_dir.get_queue(PLANNER_QUEUE_NAME)
    assert not qp.empty(), "Ожидали Event отказа в PLANNER, но очередь пуста!"
    ev_p = qp.get_nowait()
    assert ev_p.operation == "mission_rejected"
    assert ev_p.parameters == {"sender_id": "alice", "route_id": "route_9", "reason": "not_found"}

    print("✅ test_resource_manager_rejection прошёл успешно.")


if __name__ == "__main__":
    # Если запускать как скрипт
    test_access_control_allowed()
    test_access_control_denied()
    test_access_control_bad_params()
    test_resource_manager_dispatch()
    test_resource_manager_rejection()


