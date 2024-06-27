from collections import namedtuple
import requests
from socket import gethostname, gethostbyname


def read_secret_file(path: str) -> str:
    with open(path) as file:
        return file.read()


SelfIp = namedtuple("SelfIp", ["local", "external"])


def get_self_ip() -> SelfIp:
    local = gethostbyname(gethostname())
    external = requests.get("https://checkip.amazonaws.com").text.strip()
    return SelfIp(local=local, external=external)


def monkeypatch_for_template_debug():
    import collections.abc
    import inspect

    collections.Iterable = collections.abc.Iterable
    inspect.getargspec = inspect.getfullargspec
