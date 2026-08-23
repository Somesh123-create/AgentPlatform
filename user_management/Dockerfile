FROM docker.io/library/python:3.12-slim

WORKDIR /app


ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app


# ============================================================
# System dependencies
# ============================================================

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
    && rm -rf /var/lib/apt/lists/*


COPY user_management/requirements.txt ./requirements.txt

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt



# Install private agent-llm package
RUN pip install --no-cache-dir \
    "agent-llm @ git+https://github.com/Somesh123-create/AgentPlatformPackages.git@v0.1.0#subdirectory=packages/agent-llm"



COPY user_management/app ./app

RUN addgroup --system app && adduser --system --ingroup app app && \
    chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]