from abc import ABC, abstractmethod


class BaseStorage(ABC):


    @abstractmethod
    def get(self, key, default=None):

        pass


    @abstractmethod
    def set(self, key, value):

        pass


    @abstractmethod
    def delete(self, key):

        pass


    @abstractmethod
    def clear(self):

        pass
