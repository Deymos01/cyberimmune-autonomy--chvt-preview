from abc import ABC, abstractmethod
from multiprocessing import Process
from queue import Empty, Queue
from src.event_types import ControlEvent
from src.queues_dir import QueuesDirectory
from time import sleep
from src.config import DEFAULT_LOG_LEVEL, LOG_INFO, CRITICALITY_STR, LOG_ERROR
from src.config import ACCESS_CONTROL_QUEUE_NAME



class BaseAccessControlBlock(Process, ABC):
    """ Базовый класс для реализации контроля доступа """
    log_prefix = "[BASE ACCESS]"
    event_source_name = ACCESS_CONTROL_QUEUE_NAME
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
        self._log_message(LOG_INFO, "Инициализирован базовый блок контроля доступа")

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
    def _process_access_request(self, sender_id: str, route_id: str):
        """ Основная логика обработки запроса (реализуется в наследниках) """
        pass

    def stop(self):
        self._control_q.put(ControlEvent(operation='stop'))

    def run(self):
        self._log_message(LOG_INFO, "Старт обработки запросов")
        while not self._quit:
            sleep(self._recalc_interval_sec)
            try:
                self._check_control_q()
                while True:
                    event = self._events_q.get_nowait()
                    params = event.parameters
                    self._process_access_request(
                        params.get('sender_id'),
                        params.get('route_id')
                    )
            except Empty:
                continue
            except Exception as e:
                self._log_message(LOG_ERROR, f"Ошибка: {str(e)}")

