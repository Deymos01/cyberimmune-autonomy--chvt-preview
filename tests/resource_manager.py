from src.config import *
from src.event_types import Event
from src.resource_manager import BaseResourceManager
from src.queues_dir import QueuesDirectory
from src.mission_type import Mission

class ResourceManager(BaseResourceManager):

    def __init__(self, queues_dir: QueuesDirectory,
                 routes_storage: dict,  # Хранилище маршрутов
                 log_level=DEFAULT_LOG_LEVEL):
        super().__init__(queues_dir, log_level)
        self.routes_storage = routes_storage

    def _get_route_data(self, route_id: str) -> dict:
        if route_id not in self.routes_storage:
            raise ValueError(f"Маршрут {route_id} не найден")
        return self.routes_storage[route_id]

    def _dispatch_mission(self, route_data: dict):
        control_q = self._queues_dir.get_queue(CONTROL_SYSTEM_QUEUE_NAME)
        safety_q = self._queues_dir.get_queue(SAFETY_BLOCK_QUEUE_NAME)

        mission = Mission(route_data["home"], route_data["waypoints"], route_data["speed_limits"], route_data["armed"])

        control_q.put(Event(
            source=self.event_source_name,
            destination=CONTROL_SYSTEM_QUEUE_NAME,
            operation="set_mission",
            parameters=mission
        ))

        safety_q.put(Event(
            source=self.event_source_name,
            destination=SAFETY_BLOCK_QUEUE_NAME,
            operation="set_mission",
            parameters=mission
        ))

    def _send_rejection(self, sender_id: str, route_id: str, reason: str):
        planner_q = self._queues_dir.get_queue(PLANNER_QUEUE_NAME)
        planner_q.put(Event(
            source=self.event_source_name,
            destination=PLANNER_QUEUE_NAME,
            operation="mission_rejected",
            parameters={
                "sender_id": sender_id,
                "route_id": route_id,
                "reason": reason
            }
        ))
        self._log_message(LOG_DEBUG, f"Отправлен отказ для {sender_id}:{route_id}. Причина: {reason}")