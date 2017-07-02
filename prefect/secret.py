import ujson

class Secret:

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f'<Secret({self.name})>'

    def set(self, value):
        self.value = ujson.dumps(value)

    def get(self, value):
        return ujson.loads(self.value)
