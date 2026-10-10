"""Module entrypoint; workspace selection precedes loading pipeline modules."""
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
