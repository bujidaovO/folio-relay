#!/bin/zsh
# Development only: always work from the source root, beside requirements-build.txt.
cd -- "${0:A:h:h}" || exit 1
python3.12 -m venv .venv || exit 1
.venv/bin/python -m pip install -r requirements-build.txt || exit 1
.venv/bin/python build_app.py
