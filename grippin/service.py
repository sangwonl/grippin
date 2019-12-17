class Service(object):
    def __init__(self, application):
        assert application is not None
        self._application = application

    @property
    def application(self):
        return self._application

    @property
    def tracer(self):
        return self.get_application().tracer