def read_secret_file(path: str) -> str:
    with open(path) as file:
        return file.read()


def monkeypatch_for_template_debug():
    import collections.abc
    import inspect

    collections.Iterable = collections.abc.Iterable
    inspect.getargspec = inspect.getfullargspec
