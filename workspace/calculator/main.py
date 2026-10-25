"""Command-line entry point for the calculator sample."""

import argparse

from calculator import add, divide, multiply, subtract

OPERATIONS = {"add": add, "subtract": subtract, "multiply": multiply, "divide": divide}


def main() -> None:
    parser = argparse.ArgumentParser(description="Arithmetic demo")
    parser.add_argument("operation", choices=OPERATIONS)
    parser.add_argument("a", type=float)
    parser.add_argument("b", type=float)
    args = parser.parse_args()
    print(OPERATIONS[args.operation](args.a, args.b))


if __name__ == "__main__":
    main()
