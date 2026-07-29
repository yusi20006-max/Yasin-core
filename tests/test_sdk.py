from yasin_core.sdk import YasinCoreClient


def test_sdk_import_and_creation():

    client = YasinCoreClient()

    assert client is not None


def test_sdk_version_methods():

    client = YasinCoreClient()

    assert client.get_version() == "0.4.1"

    assert client.version == "0.4.1"


def test_sdk_info_methods():

    client = YasinCoreClient()

    info_dict = client.get_info()

    assert info_dict["name"] == "Yasin Core SDK Client"

    assert info_dict["version"] == "0.4.1"

    info_dict_alt = client.info()

    assert info_dict_alt == info_dict
