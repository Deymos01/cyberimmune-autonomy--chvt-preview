from src.access_control_block import BaseAccessControlBlock
from src.config import *
from src.queues_dir import QueuesDirectory
from src.event_types import Event

class AccessControlBlock(BaseAccessControlBlock):

    def __init__(self, queues_dir: QueuesDirectory,
                 allowed_mapping: dict,  # Конфигурация разрешений
                 log_level=DEFAULT_LOG_LEVEL):
        super().__init__(queues_dir, log_level)
        self.allowed_mapping = allowed_mapping

    def _process_access_request(self, sender_id: str, route_id: str):
        self._log_message(LOG_INFO,
                          f"в вызове self._process_access_request, sender_id: {sender_id}, route_id: {sender_id}")
        if not sender_id or not route_id:
            self._log_message(LOG_ERROR, "Некорректные параметры запроса")
            return

        if self._check_permissions(sender_id, route_id):
            print('fdklsjfdsjk')
            self._forward_to_resource_manager(sender_id, route_id)
        else:
            self._send_rejection(sender_id, route_id, "access_denied")

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

    def _check_permissions(self, sender_id: str, route_id: str) -> bool:
        return route_id in self.allowed_mapping.get(sender_id, [])

    def _forward_to_resource_manager(self, sender_id: str, route_id: str):
        resource_q = self._queues_dir.get_queue(RESOURCE_MANAGER_QUEUE_NAME)
        resource_q.put(Event(
            source=self.event_source_name,
            destination=RESOURCE_MANAGER_QUEUE_NAME,
            operation="take_mission",
            parameters={
                "sender_id": sender_id,
                "route_id": route_id
            }
        ))
