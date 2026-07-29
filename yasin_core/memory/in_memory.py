from yasin_core.memory.base import ShortTermMemory, LongTermMemory


class InMemoryShortTermMemory(ShortTermMemory):


    def __init__(self):

        self._data = {}


    def get(self, key, default=None):

        return self._data.get(key, default)


    def set(self, key, value):

        self._data[key] = value


    def delete(self, key):

        if key in self._data:

            del self._data[key]


    def clear(self):

        self._data.clear()


class InMemoryLongTermMemory(LongTermMemory):


    def __init__(self):

        self._data = {}


    def get(self, key, default=None):

        return self._data.get(key, default)


    def set(self, key, value):

        self._data[key] = value


    def delete(self, key):

        if key in self._data:

            del self._data[key]


    def clear(self):

        self._data.clear()
