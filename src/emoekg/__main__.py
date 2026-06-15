"""Allow ``python -m emoekg ...`` as an alternative to the ``emoekg`` script."""
from emoekg.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
