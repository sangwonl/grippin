from concurrent import futures
import sys
import time
import grpc

from . import consts


GRPC_STUB_SUFFIX = 'Stub'
GRPC_SERVICER_SUFFIX = 'Servicer'
GRPC_SERVICER_ADDER_FMT = 'add_%s_to_server'


def all_base_classes(cls):
    for c in cls.__bases__:
        if c.__name__ != 'object':
            yield c
        if c.__bases__:
            yield from all_base_classes(c)


class Application(object):
    def __init__(
            self,
            services,
            interceptors,
            port=consts.DEFAULT_GRPC_SERVER_PORT,
            max_workers=consts.DEFAULT_GRPC_NUM_THREADS,
            wakeup_interval=consts.DEFAULT_GRPC_WAKEUP_INTERVAL,
            wakeup_handler=None,
            enable_reflection=False,
            tracer=None):

        self._running = False
        self._port = port
        self._tracer = tracer
        self._wakeup_interval = wakeup_interval
        self._wakeup_handler = wakeup_handler

        self._grpc_server = self._create_grpc_server(
            max_workers, enable_reflection, services, interceptors, tracer)
        self._grpc_stubs: dict = self._populate_grpc_stubs_from_services(services)

    @property
    def port(self):
        return self._port

    @property
    def wakeup_interval(self):
        return self._wakeup_interval

    @wakeup_interval.setter
    def wakeup_interval(self, i):
        self._wakeup_interval = i

    @property
    def wakeup_handler(self):
        return self._wakeup_handler

    @wakeup_handler.setter
    def wakeup_handler(self, h):
        self._wakeup_handler = h

    def get_grpc_stub(self, svc_cls):
        return self._grpc_stubs.get(svc_cls.__name__)

    @property
    def is_running(self):
        return self._running

    @property
    def tracer(self):
        return self._tracer

    def start(self, port=None):
        self._port = port or self.port
        self._grpc_server.add_insecure_port(f'[::]:{self.port}')
        self._grpc_server.start()
        self._running = True
        try:
            while self._running:
                if self._wakeup_handler and callable(self._wakeup_handler):
                    self._wakeup_handler()
                time.sleep(self._wakeup_interval)
        except KeyboardInterrupt:
            self._grpc_server.stop(0)

    def stop(self):
        self._grpc_server.stop(0)
        self._running = False

    def _create_grpc_server(self, max_workers, enable_reflection, services, interceptors, tracer):
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
        if tracer:
            server = self._enable_trace(server, tracer)
        if enable_reflection:
            server = self._enable_reflection(server, services)
        server = self._register_services(server, services)
        server = self._register_interceptors(server, interceptors)
        return server

    def _register_services(self, server, services):
        for s_cls in services:
            svc = s_cls(self)
            for pb_rpc_mod in self._iter_modules_of_base_service(s_cls):
                service_adders = self._enumerate_service_adders(pb_rpc_mod, s_cls)

                for adder in service_adders:
                    assert callable(adder)
                    adder(svc, server)

        return server

    def _enable_reflection(self, server, services):
        from grpc_reflection.v1alpha import reflection

        service_names = [reflection.SERVICE_NAME]
        for pb_rpc_mod in self._iter_modules_of_base_service(services):
            for n in dir(pb_rpc_mod):
                if not n.endswith('_pb2'):
                    continue
                pb = getattr(pb_rpc_mod, n)
                service_names += map(lambda x: x[1].full_name, pb.DESCRIPTOR.services_by_name.items())
        reflection.enable_server_reflection(set(service_names), server)

        return server

    def _populate_grpc_stubs_from_services(self, services):
        stubs = {}
        for s_cls in services:
            svc = s_cls(self)
            for pb_rpc_mod in self._iter_modules_of_base_service(s_cls):
                grpc_servicer_cls = self._get_grpc_servicer_cls(s_cls)
                stub = self._get_grpc_stub_by_servicer(pb_rpc_mod, grpc_servicer_cls)
                stubs[s_cls.__name__] = stub
        return stubs

    def _iter_modules_of_base_service(self, svc_classes):
        svcs = svc_classes if isinstance(svc_classes, list) else [svc_classes]
        for svc_cls in svcs:
            assert self._is_grpc_service(svc_cls)
            grpc_servicer_cls = self._get_grpc_servicer_cls(svc_cls)
            if grpc_servicer_cls:
                yield sys.modules[grpc_servicer_cls.__module__]

    def _enumerate_service_adders(self, pb_rpc_mod, svc_cls):
        import inspect

        class_names = []
        func_table = {}
        grpc_servicer_cls = self._get_grpc_servicer_cls(svc_cls)
        for p in dir(pb_rpc_mod):
            prop = getattr(pb_rpc_mod, p)
            if not callable(prop):
                continue

            if inspect.isclass(prop) and prop is grpc_servicer_cls:
                class_names.append(prop.__name__)
            elif inspect.isfunction(prop):
                func_table[prop.__name__] = prop

        adders = []
        for cn in class_names:
            fn = GRPC_SERVICER_ADDER_FMT % cn
            if fn in func_table.keys():
                adders.append(func_table[fn])

        return adders

    def _get_grpc_stub_by_servicer(self, pb_rpc_mod, grpc_servicer_cls):
        import inspect

        stub_name = str(grpc_servicer_cls.__name__).replace(GRPC_SERVICER_SUFFIX, '') + GRPC_STUB_SUFFIX

        stub_class = None
        for p in dir(pb_rpc_mod):
            prop = getattr(pb_rpc_mod, p)
            if inspect.isclass(prop) and prop.__name__ == stub_name:
                stub_class = prop
                break

        return stub_class

    @staticmethod
    def _is_grpc_service(svc_cls):
        return any(GRPC_SERVICER_SUFFIX in str(s) for s in all_base_classes(svc_cls))

    @staticmethod
    def _get_grpc_servicer_cls(svc_cls):
        filtered = [s for s in all_base_classes(svc_cls) if GRPC_SERVICER_SUFFIX in str(s)]
        return filtered[0] if filtered else None

    @staticmethod
    def _register_interceptors(server, interceptors):
        return server

    def _enable_trace(self, server, tracer):
        from grpc_opentracing import open_tracing_server_interceptor
        from grpc_opentracing.grpcext import intercept_server

        tracer_interceptor = open_tracing_server_interceptor(tracer)
        return intercept_server(server, tracer_interceptor)
