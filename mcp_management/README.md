## Project Directory

    services/
    └── mcp-service/
        │
        ├── app/
        │   │
        │   ├── api/
        │   │   ├── routes/
        │   │   │   ├── mcp.py
        │   │   │   ├── versions.py
        │   │   │   ├── tools.py
        │   │   │   ├── deployments.py
        │   │   │   └── invocation.py
        │   │   │
        │   │   └── router.py
        │   │
        │   ├── core/
        │   │   ├── config.py
        │   │   ├── security.py
        │   │   └── logging.py
        │   │
        │   ├── db/
        │   │   ├── session.py
        │   │   └── base.py
        │   │
        │   ├── models/
        │   │   ├── mcp.py
        │   │   ├── mcp_version.py
        │   │   ├── mcp_tool.py
        │   │   ├── mcp_secret.py
        │   │   ├── mcp_deployment.py
        │   │   └── mcp_execution.py
        │   │
        │   ├── schemas/
        │   │   ├── mcp.py
        │   │   ├── version.py
        │   │   ├── tool.py
        │   │   └── invocation.py
        │   │
        │   ├── repositories/
        │   │   ├── mcp.py
        │   │   ├── version.py
        │   │   └── deployment.py
        │   │
        │   ├── services/
        │   │   ├── mcp_service.py
        │   │   ├── version_service.py
        │   │   ├── permission_service.py
        │   │   └── invocation_service.py
        │   │
        │   ├── runtime/
        │   │   ├── manager.py
        │   │   ├── lifecycle.py
        │   │   ├── podman.py
        │   │   └── health.py
        │   │
        │   └── main.py
        │
        ├── tests/
        │
        ├── Dockerfile
        ├── requirements.txt
        └── README.md



3. FastAPI handles management + gateway

Your FastAPI application can expose:

## MCP management
    POST   /mcps
    GET    /mcps
    GET    /mcps/{id}
    PATCH  /mcps/{id}
    DELETE /mcps/{id}
## Versions
    POST /mcps/{id}/versions
    GET  /mcps/{id}/versions
    GET  /mcps/{id}/versions/{version}
## Tools
    GET  /mcps/{id}/tools
    PATCH /mcps/{id}/tools
## Deployment
    POST /mcps/{id}/versions/{version}/deploy
    POST /mcps/{id}/versions/{version}/undeploy
## Invocation
    POST /mcps/{id}/invoke

## So externally it's simply:

                 MCP Service
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
    Management     Build       Invocation
        API        System        API