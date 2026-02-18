VENV=.venv
PYTHON=$(VENV)/bin/python
PIP=$(VENV)/bin/pip
APP=app.main:app
HOST=0.0.0.0
PORT=8000

.PHONY: venv install run test clean docker-build docker-up docker-down

venv:
	python3 -m venv $(VENV)

install: venv
	$(PYTHON) -m pip install --upgrade pip
	$(PIP) install -r requirements.txt

run:
	$(PYTHON) -m uvicorn $(APP) --reload --host $(HOST) --port $(PORT)

test:
	$(PYTHON) -m pytest -q

clean:
	rm -rf uploads/* converted/*
	rm -f state.json

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down
