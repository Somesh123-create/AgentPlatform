# AgentPlatform — AI Coding Agent Guide

This document helps AI coding agents understand the AgentPlatform codebase and be immediately productive.

## Project Overview

**AgentPlatform** is a multi-service application platform with the following components:

- **`packages/agent-llm`**: Reusable LLM abstraction layer supporting multiple providers (Groq, NVIDIA, OpenAI)
- **`postgresql/`**: PostgreSQL database with pgvector extension for vector search
- **`redis/`**: Redis cache/queue service
- **`user_management/`**: FastAPI-based user management service with authentication, authorization, and API routes

Services are orchestrated via `compose.yml` using Docker/Podman.

### Key Directories

| Directory | Purpose |
|-----------|---------|
| `packages/agent-llm/src/agent_llm/` | LLM client, providers, models, routing |
| `packages/agent-llm/tests/` | Unit tests for LLM client and providers |
| `user_management/app/` | FastAPI application (routes, services, models) |
| `postgresql/init/` | Database initialization scripts (pgvector) |
| `compose.yml` | Docker orchestration for all services |

## Build & Run Commands

```bash
## Build

```bash
# Build all services defined in compose file
podman-compose build

# Build without using cache
podman-compose build --no-cache

# Build and start in one go
podman-compose up -d --build

# Build Images
podman-compose up -d --build 
```

### Local Development

```bash
# Start all services (PostgreSQL, Redis, User Management)
podman-compose up -d

# Or with Docker Compose
docker compose up -d

# View logs
podman-compose logs -f        # All services
podman-compose logs -f user-management  # User management service only

# Stop all services
podman-compose down

# Restart services
podman-compose restart
```

### User Management API

```bash
# Run user management directly (without full compose)
cd user_management
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Or using the task runner (if available)
# See tasks.json for available shortcuts
```

### Testing

```bash
# Run all tests
cd packages/agent-llm
pytest

# Run tests with verbose output
pytest -v

# Run specific test files
pytest packages/agent-llm/tests/test_client.py

# Run tests with coverage
pytest --cov=agent_llm
```

## Key Conventions & Patterns

### Python & FastAPI

- **Python 3.12+** with type hints throughout
- **FastAPI** with async/await for all endpoints
- **SQLAlchemy async** with `asyncpg` for PostgreSQL operations
- Dependencies injected via `Depends()` in FastAPI routes

### LLM Provider Pattern (`packages/agent-llm`)

The LLM abstraction follows a provider pattern:

1. **`LLMProvider`** (abstract base) defines `generate()` and `stream()` methods
2. **Concrete providers** (`GroqProvider`, `NVIDIAProvider`, `OpenAIProvider`) implement the interface
3. **`ProviderRouter`** routes requests to the appropriate provider
4. **`LLMClient`** is the main entry point that uses the router

**Key files:**
- `src/agent_llm/providers/base.py` — Abstract base class
- `src/agent_llm/providers/groq.py` — Groq implementation
- `src/agent_llm/providers/nvidia.py` — NVIDIA implementation
- `src/agent_llm/providers/openai.py` — OpenAI implementation
- `src/agent_llm/routing/router.py` — Provider routing logic
- `src/agent_llm/models/message.py` — Message model (system/user/assistant/tool)
- `src/agent_llm/models/response.py` — LLM response model with usage tracking

### User Management Pattern (`user_management/`)

Follows a repository-service pattern:

1. **Routes** (`app/api/routes/`) — FastAPI endpoints
2. **Services** (`app/services/`) — Business logic
3. **Repositories** (`app/repositories/`) — Data access layer
4. **Models** (`app/models/`) — SQLAlchemy ORM models
5. **Schemas** (`app/schemas/`) — Pydantic models for request/response validation

**Key files:**
- `app/core/config.py` — Pydantic settings with `.env` integration
- `app/core/database.py` — SQLAlchemy async engine and session management
- `app/core/security.py` — JWT token creation and password verification
- `app/utils/password.py` — bcrypt password hashing/verification
- `app/models/user.py` — SQLAlchemy User model with role enum
- `app/repositories/user_repository.py` — User data access operations

### Environment Configuration

- All environment variables defined in `.env` and `.env.example`
- Use `${VAR:-default}` syntax in `compose.yml` for compose variable substitution
- Settings loaded via Pydantic `BaseSettings` with `SettingsConfigDict(env_file=".env")`
- Key variables: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `JWT_SECRET_KEY`

### Database (PostgreSQL + pgvector)

- **pgvector** extension enabled via init script mounted in `compose.yml`
- Vector operations use `pgvector` functions (e.g., `<=>` for cosine distance)
- Async SQLAlchemy engine configured in `user_management/app/core/database.py`
- Migrations not currently used — models created via `Base.metadata.create_all()` during startup

### Authentication & Authorization

- **JWT tokens** for session management
- Passwords hashed with **bcrypt** (cost factor implicit, ~60 bytes max)
- OAuth2 password flow for login/registration
- Password validation: max 72 bytes UTF-8

### Code Style & Formatting

- Black formatter, isort for imports
- Pydantic v2 for models and settings
- Async SQLAlchemy patterns (`async with session()`)
- `raise ValueError(...)` for business logic errors
- `raise HTTPException(status_code=..., detail=...)` for API errors

## Common Pitfalls & Gotchas

| Issue | Solution/Workaround |
|-------|---------------------|
| **pgvector not working** | Ensure `./postgresql/init/enable-vector.sql` is mounted in `compose.yml` |
| **Environment variables not loaded** | Check that `.env` file exists in the working directory; compose uses `.env` automatically |
| **Running pip outside Docker** | Dependencies are installed during Docker build only; use `podman-compose exec user-management pip install ...` for container installs |
| **bcrypt password hash mismatch** | Ensure `hash_password()` and `verify_password()` are used consistently; passwords > 72 bytes will fail |
| **JWT token expiration** | Tokens expire in 30 minutes (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`); refresh logic in `auth_service.py` |
| **Redis connection issues** | Verify `REDIS_PASSWORD` is set in `.env`; Redis requires authentication |
| **Import errors in agent-llm** | Ensure you're running from the correct directory; package installed in `agent-llm.egg-info/` |
| **Async session not closed** | Always ensure `get_db()` generator is consumed or use `async with` pattern |
| **Model routing errors** | Check `ProviderRouter.get_provider()` — raises `ValueError` for unsupported providers |

## Linked Documentation

- `compose.yml` — Full service definitions, network config, and environment variable mappings
- `postgresql/init/enable-vector.sql` — pgvector initialization script
- `user_management/requirements.txt` — Pinned Python dependencies
- `user_management/app/core/config.py` — Settings configuration and environment variables
- `.env.example` — Template for environment variables
- `packages/agent-llm/pyproject.toml` — Package metadata and dependencies
- `packages/agent-llm/tests/` — Test patterns and examples

## Quick Start for New Agents

1. **Start the infrastructure**:
   ```bash
   cd /home/somesh/AgentPlatform
   podman-compose up -d  # or: docker compose up -d
   ```

2. **Verify services are running**:
   ```bash
   podman-compose ps
   # Should show: postgres, redis, user-management
   ```

3. **Start the user management API** (if not running via compose):
   ```bash
   cd user_management
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

4. **Test the API**:
   ```bash
   # Health check
   curl http://localhost:8000/health

   # Register a new user
   curl -X POST http://localhost:8000/auth/register \
     -H "Content-Type: application/json" \
     -d '{"name":"Test User","email":"test@example.com","password":"secret123"}'

   # Get health with Redis status
   curl http://localhost:8000/health
   ```

5. **Run the LLM tests** (requires API keys):
   ```bash
   cd packages/agent-llm
   GROQ_API_KEY=your_key pytest tests/test_groq_provider.py
   ```

## Agent-Specific Tips

- **When adding a new LLM provider**: Follow the pattern in `packages/agent-llm/src/agent_llm/providers/` — implement `LLMProvider` abstract methods `generate()` and `stream()`.
- **When adding new API routes**: Follow the repository-service pattern in `user_management/app/api/routes/`.
- **When debugging database issues**: Check the async engine configuration in `user_management/app/core/database.py` and ensure pgvector is enabled.
- **When adding environment variables**: Update both `.env` and `.env.example`; update `compose.yml` if the variable is used in service configuration.