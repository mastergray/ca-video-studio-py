# Contributing

## Repository practices

- The default branch is `main`.
- This is a personal `mastergray` project. A future GitHub SSH remote should use the `github-mastergray` host alias.
- Keep Git identity repository-local when it must differ from the global personal identity.
- Commit messages use a short summary line, followed by a blank line and details when useful.
- Do not add automated `Co-Authored-By` trailers.
- Do not commit generated videos, virtual environments, caches, IDE state, or local AI-tool state.

## Python conventions

This project follows the local Python class style guide used during project initialization:

- Classes use `CapitalizedCamelCase`.
- Methods and multiword variables use `camelCase`.
- Instance attributes are private-by-convention `_camelCase` values exposed through properties when needed.
- Module constants use `UPPERCASE_WITH_UNDERSCORES`.
- Every method has type hints and a Hindley-Milner-inspired signature comment.
- Class members are ordered as class variables, constructor, dunder methods, properties, instance methods, protected methods, private methods, class methods, then static methods.
- Imports state their purpose with an inline comment.
- Module docstrings are not used; concise `#` comments are preferred.
- Qt override names such as `resizeEvent` and `closeEvent` retain the framework-required spelling.

The code currently uses Python 3.10-compatible syntax. Development and runtime validation are performed with the Python 3.11 interpreter available on the target Ubuntu system; no unnecessary upper Python bound is imposed by this project.

## Verification

Before committing:

```bash
uv sync
uv run ruff check src tests
QT_QPA_PLATFORM=offscreen uv run pytest
uv run ca-video-studio-py validate examples/life.cav.json
```
