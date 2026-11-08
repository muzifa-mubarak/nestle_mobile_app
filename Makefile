dev:
	docker compose up --build

seed:
	docker compose exec api python scripts/seed.py

down:
	docker compose down
