class ResearchError(Exception):
    """Only safe, prewritten messages may cross the API boundary."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class BudgetExhausted(ResearchError):
    pass


class RunCancelled(ResearchError):
    pass
