# Contributing

Use Python 3.11 or newer on Windows. Create a virtual environment, install the
project with `pip install -e ".[dev]"`, and run `python -m pytest` before a
pull request.

Do not commit personal profiles, Zotero exports, email recipients, runtime
state, generated newsletters, or credentials. Preserve the invariant that
`state/processed.json` changes only after a confirmed email send.
