class Service(object):
    def __init__(self, application):
        assert application is not None
        self._application = application

    def get_application(self):
        return self._application

    def get_tracer(self):
        return self.get_application().tracer