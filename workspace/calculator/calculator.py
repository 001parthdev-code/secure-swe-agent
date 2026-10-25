"""Small arithmetic library for testing Secure SWE Agent code proposals."""


def add(a: float, b: float) -> float:
    return a + b


def subtract(a: float, b: float) -> float:
    # Intentional bug for the agent to discover and correct.
    return a + b


def multiply(a: float, b: float) -> float:
    return a * b


def divide(a: float, b: float) -> float:
    if b == 0:
        raise ZeroDivisionError("cannot divide by zero")
    return a / b
