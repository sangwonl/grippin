import unittest
import grpc

from multiprocessing import Process


g_port = 50050


class TestServiceProxy(object):
    def __init__(self, app, svc_cls):
        super().__init__()

        channel = grpc.insecure_channel(f'localhost:{app.port}')
        object.__setattr__(self, 'stub', app.get_grpc_stub(svc_cls)(channel))

    def __getattribute__(self, name):
        stub = object.__getattribute__(self, 'stub')
        return object.__getattribute__(stub, name)


class TestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = self.get_app()
        self.running_server = None

    def _run_grpc_server_app(self, app, rand_port):
        self.running_server = Process(target=self.app.start, args=(rand_port,))
        self.running_server.start()

    def setUp(self):
        super().setUp()

        global g_port
        g_port += 1

        self._run_grpc_server_app(self.app, g_port)

    def tearDown(self):
        super().tearDown()
        self.running_server.terminate()

    def get_app(self):
        raise NotImplementedError('Method not implemented!')

    def service_proxy(self, svc_class):
        return TestServiceProxy(self.app, svc_class)
