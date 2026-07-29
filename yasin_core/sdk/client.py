from yasin_core.version import VERSION


class YasinCoreClient:


    def __init__(self):

        self._version = VERSION


    @property
    def version(self) -> str:

        return self._version


    def get_version(self) -> str:

        return self._version


    def info(self) -> dict:

        return self.get_info()


    def get_info(self) -> dict:

        return {
            "name": "Yasin Core SDK Client",
            "version": self._version
        }
