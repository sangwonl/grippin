import unittest
import grpc
import threading


g_port = 50050


def getattr(obj, name):
    return object.__getattribute__(obj, name)


def setattr(obj, name, val):
    object.__setattr__(obj, name, val)


class TestServiceProxy(object):
    def __init__(self, app, svc_cls):
        super().__init__()

        channel = grpc.insecure_channel(f'localhost:{app.port}')
        setattr(self, 'stub', app.get_grpc_stub(svc_cls)(channel))

    def __getattribute__(self, name):
        stub = getattr(self, 'stub')
        return getattr(stub, name)


class TestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = self.get_app()
        self.stopEvent: threading.Event = None

    def _gprc_server_runner(self, app, rand_port):
        def stopper():
            if self.stopEvent.is_set():
                app.stop()

        app.wakeup_interval = 0
        app.wakeup_handler = stopper

        app.start(rand_port)

    def _run_grpc_server_app(self, app, rand_port):
        threading.Thread(target=self._gprc_server_runner, args=(self.app, rand_port)).start()
        self.stopEvent = threading.Event()

    def _stop_grpc_server_app(self):
        self.stopEvent.set()

    def setUp(self):
        super().setUp()

        global g_port
        g_port += 1

        self._run_grpc_server_app(self.app, g_port)

    def tearDown(self):
        super().tearDown()

        self._stop_grpc_server_app()

    def get_app(self):
        raise NotImplementedError('Method not implemented!')

    def service_proxy(self, svc_class):
        return TestServiceProxy(self.app, svc_class)
