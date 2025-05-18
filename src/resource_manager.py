from abc import ABC, abstractmethod
from multiprocessing import Process
from src.config import RESOURCE_MANAGER_QUEUE_NAME
from queue import Empty, Queue
from src.event_types import ControlEvent
from src.queues_dir import QueuesDirectory
from time import sleep
from src.config import DEFAULT_LOG_LEVEL, LOG_INFO, CRITICALITY_STR, LOG_ERROR

class BaseResourceManager(Process, ABC):
    """ Базовый класс для управления ресурсами """
    log_prefix = "[BASE RESOURCE]"
    event_source_name = RESOURCE_MANAGER_QUEUE_NAME
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

    @abstractmethod
    def _send_rejection(self, sender_id: str, route_id: str, reason: str):
        pass


    def run(self):
        self._log_message(LOG_INFO, "Старт обработки маршрутов")
        while not self._quit:
            sleep(self._recalc_interval_sec)
            try:
                self._check_control_q()

                try:
                    event = self._events_q.get_nowait()

                    # Проверка наличия обязательных параметров
                    if 'sender_id' not in event.parameters or 'route_id' not in event.parameters:
                        raise KeyError("Отсутствуют обязательные параметры sender_id или route_id")

                    route_id = event.parameters['route_id']
                    sender_id = event.parameters['sender_id']

                    try:
                        route_data = self._get_route_data(route_id)
                        self._dispatch_mission(route_data)
                        self._log_message(LOG_INFO, f"Маршрут {route_id} успешно отправлен")

                    except ValueError as e:
                        self._log_message(LOG_ERROR, str(e))
                        self._send_rejection(sender_id, route_id, "route_not_found")

                except KeyError as e:
                    self._log_message(LOG_ERROR, f"Некорректный запрос: {str(e)}")
                    self._send_rejection("unknown", "unknown", "invalid_request_format")

            except Empty:
                continue

            except Exception as e:
                self._log_message(LOG_ERROR, f"Критическая ошибка: {str(e)}")
                self._send_rejection("unknown", "unknown", "internal_server_error")


    @abstractmethod
    def _dispatch_mission(self, mission_data: dict):
        pass
