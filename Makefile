.PHONY: check test lint build dev install

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

lint:
	cd backend && ruff check . && ruff format --check . && mypy trucksafe/domain trucksafe/services
	cd frontend && npm run lint

test:
	cd backend && pytest -q
	cd frontend && npm test -- --run

build:
	cd frontend && npm run build

check:
	cd backend && ruff check . && ruff format --check . && mypy trucksafe/domain trucksafe/services && pytest -q
	cd frontend && npm run lint && npm run typecheck && npm test -- --run && npm run build

dev-backend:
	cd backend && python manage.py runserver 0.0.0.0:8000

dev-frontend:
	cd frontend && npm run dev
