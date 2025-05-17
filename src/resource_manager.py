from abc import ABC, abstractmethod
from multiprocessing import Process
from config import CONTROL_SYSTEM_QUEUE_NAME, SAFETY_BLOCK_QUEUE_NAME
from queue import Empty, Queue
from event_types import Event, ControlEvent
from queues_dir import QueuesDirectory
from time import sleep
from config import DEFAULT_LOG_LEVEL, LOG_INFO, CRITICALITY_STR, LOG_ERROR

class BaseResourceManager(Process, ABC):
    """ Базовый класс для управления ресурсами """
    log_prefix = "[BASE RESOURCE]"
    event_source_name = "resource_manager_base_queue"
    events_q_name = event_source_name

    def __init__(self, queues_dir: QueuesDirectory, log_level=DEFAULT_LOG_LEVEL):
        super().__init__()
        self._queues_dir = queues_dir
        self.log_level = log_level

        # Инициализация очередей
        self._events_q = Queue()
        self._control_q = Queue()
        self._quit = False
        self._recalc_interval_sec = 0.1

        self._queues_dir.register(self._events_q, self.events_q_name)
        self._log_message(LOG_INFO, "Инициализирован базовый менеджер ресурсов")

    def _log_message(self, criticality: int, message: str):
        if criticality <= self.log_level:
            print(f"[{CRITICALITY_STR[criticality]}]{self.log_prefix} {message}")

    def _check_control_q(self):
        try:
            request: ControlEvent = self._control_q.get_nowait()
            if isinstance(request, ControlEvent) and request.operation == 'stop':
                self._quit = True
        except Empty:
            pass

    @abstractmethod
    def _get_route_data(self, route_id: str) -> dict:
        """ Получение данных маршрута (реализуется в наследниках) """
        pass

    def stop(self):
        self._control_q.put(ControlEvent(operation='stop'))

    def run(self):
        self._log_message(LOG_INFO, "Старт обработки маршрутов")
        while not self._quit:
            sleep(self._recalc_interval_sec)
            try:
                self._check_control_q()
                event = self._events_q.get_nowait()
                route_data = self._get_route_data(event.parameters['route_id'])

                mission_data = {
                    "sender_id": event.parameters['sender_id'],
                    "route": route_data
                }

                self._dispatch_mission(mission_data)

            except Empty:
                continue
            except Exception as e:
                self._log_message(LOG_ERROR, f"Ошибка: {str(e)}")

    def _dispatch_mission(self, mission_data: dict):
        control_q = self._queues_dir.get_queue(CONTROL_SYSTEM_QUEUE_NAME)
        safety_q = self._queues_dir.get_queue(SAFETY_BLOCK_QUEUE_NAME)

        control_q.put(Event(
            source=self.event_source_name,
            destination=CONTROL_SYSTEM_QUEUE_NAME,
            operation="set_mission",
            parameters=mission_data
        ))

        safety_q.put(Event(
            source=self.event_source_name,
            destination=SAFETY_BLOCK_QUEUE_NAME,
            operation="set_mission",
            parameters=mission_data
        ))
