# Auto VEdit — common tasks.
# macOS uses a venv on LOCAL disk: OneDrive dehydrates files into cloud
# placeholders whose reads hang forever (see docs/setup-mac.md).
VENV ?= $(HOME)/.venvs/capcut-mac
PY   := $(VENV)/bin/python

.PHONY: setup test lint clean help

help:
	@echo "make setup   create the venv, install deps + headless Chromium"
	@echo "make test    run the test suite (needs ffmpeg on PATH)"
	@echo "make clean   remove __pycache__ and .pytest_cache"

setup:
	python3 -m venv $(VENV)
	$(PY) -m pip install -r requirements.txt
	$(PY) -m pip install pytest
	$(PY) -m playwright install chromium

test:
	PATH="$(VENV)/bin:$$PATH" $(PY) -m pytest

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache
