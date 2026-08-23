FROM docker.io/library/python:3.12-slim

WORKDIR /app

# Git + SSH required to install private GitHub package
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        openssh-client \
    && rm -rf /var/lib/apt/lists/*


# Configure GitHub host
RUN mkdir -p -m 0700 /root/.ssh \
    && ssh-keyscan github.com >> /root/.ssh/known_hosts


ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

    
COPY user_management/requirements.txt ./requirements.txt

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt



# Install private agent-llm package
RUN --mount=type=ssh \
    pip install --no-cache-dir \
    "agent-llm @ git+ssh://git@github.com/Somesh123-create/AgentPlatformPackages.git@v0.1.0#subdirectory=packages/agent-llm"


COPY user_management/app ./app

RUN addgroup --system app && adduser --system --ingroup app app && \
    chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]