from yasin_core.memory.base import LongTermMemory
from yasin_core.storage.base import BaseStorage


class StorageBackedLongTermMemory(LongTermMemory):


    def __init__(self, storage: BaseStorage):

        self.storage = storage


    def get(self, key, default=None):

        return self.storage.get(key, default)


    def set(self, key, value):

        self.storage.set(key, value)


    def delete(self, key):

        self.storage.delete(key)


    def clear(self):

        self.storage.clear()
