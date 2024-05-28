class Record:
    """
    Avoiding Pydantic until v2 migration is complete.
    """

    def __init__(self, key: str = None):
        self.key = key
