import json
import os
from yasin_core.storage.base import BaseStorage


class JSONFileStorage(BaseStorage):


    def __init__(self, filepath):

        self.filepath = filepath

        self._data = {}

        self.load()


    def load(self):

        if os.path.exists(self.filepath):

            try:

                with open(self.filepath, "r", encoding="utf-8") as f:

                    self._data = json.load(f)

            except Exception:

                self._data = {}

        else:

            self._data = {}


    def save(self):

        dir_path = os.path.dirname(self.filepath)

        if dir_path and not os.path.exists(dir_path):

            os.makedirs(dir_path, exist_ok=True)


        with open(self.filepath, "w", encoding="utf-8") as f:

            json.dump(self._data, f, indent=4)


    def get(self, key, default=None):

        return self._data.get(key, default)


    def set(self, key, value):

        self._data[key] = value

        self.save()


    def delete(self, key):

        if key in self._data:

            del self._data[key]

            self.save()


    def clear(self):

        self._data.clear()

        self.save()
