"""Explicit fixed Business12 entrypoint; no caller-selectable family."""
from cli import main
if __name__ == '__main__': raise SystemExit(main(family='business12'))
