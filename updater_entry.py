"""Independent temporary updater executable entry point."""

import argparse
import multiprocessing
from updater.transaction import run_transaction


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--transaction", required=True)
    args = parser.parse_args()
    return 0 if run_transaction(args.transaction) == "committed" else 1


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
