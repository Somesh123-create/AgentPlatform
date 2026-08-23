# Agent Customization

This project is a platform with PostgreSQL (pgvector), Redis, and a FastAPI user management service. See `compose.yml` for the full infrastructure.

## Project Overview

- **PostgreSQL**: `postgresql/` with `pgvector` extension enabled via `init/enable-vector.sql`
- **Redis**: `redis/` for caching/queuing
- **User Management**: `user_management/` — FastAPI app (Python 3.12, `requirements.txt`)

Services are orchestrated via `compose.yml`.

## Build & Run

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

The FastAPI app runs on port 8000 (see `user_management/Dockerfile`).

## Key Conventions

- **Dockerfiles**: All services use `FROM <image>:<tag>` with `EXPOSE` declared
- **Environment**: `.env` variables are used (see `.env.example`); always reference via `${VAR:-default}`
- **PostgreSQL**: pgvector is enabled by mounting `./postgresql/init/enable-vector.sql` to `/docker-entrypoint-initdb.d/`
- **Python**: `user_management/requirements.txt` pins `bcrypt==4.1.2`; use `uvicorn app.main:app` to run

## Common Pitfalls

- Forgetting to mount the pgvector init SQL in `compose.yml` — vector functions won't work
- Environment variables not loaded from `.env` — always check `compose.yml` for `${VAR:-default}` patterns
- Running `pip install` outside the Docker build — dependencies are installed in the Dockerfile only

## Linked Documentation

- `compose.yml` — full service definitions and network config
- `postgresql/init/enable-vector.sql` — pgvector initialization
- `user_management/requirements.txt` — dependency list
- `.env.example` — environment variable templates