# Contributing

Contributions are welcome through focused issues and pull requests.

## Development setup

```bash
git clone https://github.com/mhdihso/procora.git
cd procora
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[all,dev]'
```

Run the required checks before opening a pull request:

```bash
ruff check procora tests examples
mypy procora
pytest -m 'not integration' --cov=procora --cov-fail-under=80
python -m build
```

Integration tests create and drop database objects. Run them only against dedicated
disposable databases using the variables documented in `.env.example`:

```bash
pytest -m integration
```

Keep changes small, add a regression test for every bug fix, update documentation when
behavior changes, and do not commit credentials or production connection strings.

