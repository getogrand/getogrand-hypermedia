def read_secret_file(path: str) -> str:
    with open(path) as file:
        return file.read()
