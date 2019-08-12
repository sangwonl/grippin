from concurrent import futures
import sys
import time
import grpc

from . import consts


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

        self._wakeup_interval = wakeup_interval
        self._wakeup_handler = wakeup_handler

        server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
        server.add_insecure_port(f'[::]:{port}')

        if tracer:
            server = self._enable_trace(server, tracer)

        if enable_reflection:
            server = self._enable_reflection(server, services)

        server = self._register_services(server, services)
        server = self._register_interceptors(server, interceptors)

        self._grpc_server = server

    @staticmethod
    def _enumerate_service_adders(pb_rpc_mod):
        import inspect

        class_names = []
        func_table = {}
        for p in dir(pb_rpc_mod):
            prop = getattr(pb_rpc_mod, p)
            if not callable(prop):
                continue

            if inspect.isclass(prop):
                class_names.append(prop.__name__)
            elif inspect.isfunction(prop):
                func_table[prop.__name__] = prop

        adders = []
        for cn in class_names:
            fn = f'add_{cn}_to_server'
            if fn in func_table.keys():
                adders.append(func_table[fn])

        return adders

    @staticmethod
    def _iter_modules_of_base_service(svc_classes):
        svcs = svc_classes if isinstance(svc_classes, list) else [svc_classes]
        for svc_cls in svcs:
            for base_cls in svc_cls.__bases__:
                if 'grippin.service.Service' in str(base_cls):
                    continue
                yield sys.modules[base_cls.__module__]

    def _register_services(self, server, services):
        for s_cls in services:
            svc = s_cls(self)
            for pb_rpc_mod in self._iter_modules_of_base_service(s_cls):
                service_adders = self._enumerate_service_adders(pb_rpc_mod)

                for adder in service_adders:
                    assert callable(adder)
                    adder(svc, server)

        return server

    @staticmethod
    def _register_interceptors(server, interceptors):
        return server

    def _enable_trace(self, server, tracer):
        from grpc_opentracing import open_tracing_server_interceptor
        from grpc_opentracing.grpcext import intercept_server

        tracer_interceptor = open_tracing_server_interceptor(tracer)
        self.tracer = tracer

        return intercept_server(server, tracer_interceptor)

    def _enable_reflection(self, server, services):
        from grpc_reflection.v1alpha import reflection

        service_names = [reflection.SERVICE_NAME]
        for pb_rpc_mod in self._iter_modules_of_base_service(services):
            for n in dir(pb_rpc_mod):
                if not n.endswith('_pb2'):
                    continue
                pb = getattr(pb_rpc_mod, n)
                service_names += list(map(lambda x: x[1].full_name, pb.DESCRIPTOR.services_by_name.iteritems()))
        reflection.enable_server_reflection(service_names, server)

        return server

    def start(self):
        self._grpc_server.start()
        try:
            while True:
                if self._wakeup_handler and callable(self._wakeup_handler):
                    self._wakeup_handler()
                time.sleep(self._wakeup_interval)
        except KeyboardInterrupt:
            self._grpc_server.stop(0)
