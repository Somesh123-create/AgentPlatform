from datetime import datetime, timezone

import httpx
from cryptography.fernet import InvalidToken
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from app.core.encryption import encrypt_secret
from app.core.encryption import decrypt_secret
from app.models.llm import ConnectionTestStatus, CredentialStatus, LLMModel, LLMModelAccess, LLMProvider, LLMProviderCredential, LLMStatus

SEED = {
    "openai": [("gpt-4.1-mini", "GPT-4.1 Mini")],
    "google": [("gemini-2.0-flash", "Gemini 2.0 Flash")],
    "anthropic": [("claude-3-5-haiku-latest", "Claude 3.5 Haiku")],
    "groq": [("llama-3.3-70b-versatile", "Llama 3.3 70B")],
    "nvidia": [("meta/llama-3.1-70b-instruct", "Llama 3.1 70B")],
    "azure": [("gpt-4.1-mini", "Azure GPT-4.1 Mini")],
}

def _provider_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict) and isinstance(error.get("message"), str):
                return error["message"][:450]
            if isinstance(payload.get("detail"), str):
                return payload["detail"][:450]
            if isinstance(payload.get("title"), str):
                return payload["title"][:450]
    except ValueError:
        pass
    return f"Provider returned HTTP {response.status_code}."

async def seed_catalog(db):
    for slug, models in SEED.items():
        provider = (await db.execute(select(LLMProvider).where(LLMProvider.slug == slug))).scalar_one_or_none()
        if provider is None:
            provider = LLMProvider(slug=slug, display_name=slug.title(), api_family="openai_compatible" if slug in {"openai", "azure", "groq", "nvidia"} else slug)
            db.add(provider)
            await db.flush()
        for model_name, display_name in models:
            exists = (await db.execute(select(LLMModel).where(LLMModel.provider_id == provider.id, LLMModel.model_name == model_name))).scalar_one_or_none()
            if exists is None:
                db.add(LLMModel(provider_id=provider.id, model_name=model_name, display_name=display_name, capabilities={"tools": True, "streaming": True}))
    await db.commit()

async def list_models(db, owner_id: int):
    result = await db.execute(select(LLMModel, LLMProvider, LLMModelAccess).join(LLMProvider, LLMProvider.id == LLMModel.provider_id).outerjoin(LLMModelAccess, (LLMModelAccess.model_id == LLMModel.id) & (LLMModelAccess.owner_id == owner_id)).where(LLMModel.status == LLMStatus.ACTIVE).order_by(LLMProvider.display_name, LLMModel.display_name))
    return list(result.all())

async def create_model(db, data):
    provider = (await db.execute(select(LLMProvider).where(LLMProvider.id == data.provider_id))).scalar_one_or_none()
    if provider is None:
        return None
    model = LLMModel(provider_id=provider.id, model_name=data.model_name, display_name=data.display_name, capabilities=data.capabilities, context_window=data.context_window, max_output_tokens=data.max_output_tokens)
    db.add(model)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise
    await db.refresh(model)
    return model

async def get_model(db, model_id: int):
    return (await db.execute(select(LLMModel).where(LLMModel.id == model_id))).scalar_one_or_none()

async def update_model(db, model, data):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(model, field, value)
    await db.commit()
    await db.refresh(model)
    return model

async def delete_model(db, model_id: int):
    model = await get_model(db, model_id)
    if model is None:
        return False
    await db.execute(delete(LLMModel).where(LLMModel.id == model_id))
    await db.commit()
    return True

async def set_access(db, owner_id: int, model_id: int, enabled: bool):
    access = (await db.execute(select(LLMModelAccess).where(LLMModelAccess.owner_id == owner_id, LLMModelAccess.model_id == model_id))).scalar_one_or_none()
    if access is None:
        access = LLMModelAccess(owner_id=owner_id, model_id=model_id, enabled=enabled)
        db.add(access)
    else:
        access.enabled = enabled
    await db.commit()
    return access

async def set_default(db, owner_id: int, model_id: int):
    access = await set_access(db, owner_id, model_id, True)
    rows = await db.execute(select(LLMModelAccess).where(LLMModelAccess.owner_id == owner_id))
    for row in rows.scalars():
        row.is_default = row.model_id == model_id
    await db.commit()
    return access

async def test_model_connection(db, owner_id: int, model_id: int):
    model_row = (await db.execute(select(LLMModel, LLMProvider).join(LLMProvider, LLMProvider.id == LLMModel.provider_id).where(LLMModel.id == model_id))).one_or_none()
    if model_row is None:
        return None
    model, provider = model_row
    credential = (await db.execute(select(LLMProviderCredential).where(LLMProviderCredential.owner_id == owner_id, LLMProviderCredential.provider_id == provider.id))).scalar_one_or_none()
    access = (await db.execute(select(LLMModelAccess).where(LLMModelAccess.owner_id == owner_id, LLMModelAccess.model_id == model_id))).scalar_one_or_none()
    if access is None:
        access = LLMModelAccess(owner_id=owner_id, model_id=model_id)
        db.add(access)
    tested_at = datetime.now(timezone.utc)
    status = ConnectionTestStatus.FAILED
    error = None
    if credential is None:
        error = "No provider credential configured."
    else:
        try:
            api_key = decrypt_secret(credential.ciphertext)
            if provider.api_family == "openai_compatible":
                compatible_urls = {
                    "openai": "https://api.openai.com/v1/chat/completions",
                    "groq": "https://api.groq.com/openai/v1/chat/completions",
                    "nvidia": "https://integrate.api.nvidia.com/v1/chat/completions",
                }
                url = compatible_urls.get(provider.slug)
                if not url:
                    status = ConnectionTestStatus.UNSUPPORTED
                    error = f"Connection testing is not configured for provider '{provider.slug}'."
                    access.last_test_status = status
                    access.last_tested_at = tested_at
                    access.last_test_error = error
                    await db.commit()
                    return model_id, status, tested_at, error
                payload = {"model": model.model_name, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}
                async with httpx.AsyncClient(timeout=15) as client:
                    response = await client.post(url, headers={"Authorization": f"Bearer {api_key}"}, json=payload)
                if response.is_success:
                    status = ConnectionTestStatus.SUCCEEDED
                else:
                    error = _provider_error(response)
            elif provider.slug == "anthropic":
                payload = {"model": model.model_name, "max_tokens": 1, "messages": [{"role": "user", "content": "ping"}]}
                async with httpx.AsyncClient(timeout=15) as client:
                    response = await client.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"}, json=payload)
                if response.is_success:
                    status = ConnectionTestStatus.SUCCEEDED
                else:
                    error = _provider_error(response)
            elif provider.slug == "google":
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model.model_name}:generateContent?key={api_key}"
                async with httpx.AsyncClient(timeout=15) as client:
                    response = await client.post(url, json={"contents": [{"parts": [{"text": "ping"}]}]})
                if response.is_success:
                    status = ConnectionTestStatus.SUCCEEDED
                else:
                    error = _provider_error(response)
            else:
                status = ConnectionTestStatus.UNSUPPORTED
                error = f"Connection testing is not implemented for provider '{provider.slug}'."
        except InvalidToken:
            error = "Stored credential cannot be decrypted; save the provider key again."
        except httpx.TimeoutException:
            error = "Provider request timed out."
        except httpx.HTTPError as exc:
            error = f"Provider request failed: {type(exc).__name__}."
        except (ValueError, KeyError) as exc:
            error = type(exc).__name__
    access.last_test_status = status
    access.last_tested_at = tested_at
    access.last_test_error = error
    await db.commit()
    return model_id, status, tested_at, error

async def complete_model(db, owner_id: int, model_id: int, data):
    model_row = (await db.execute(select(LLMModel, LLMProvider).join(LLMProvider, LLMProvider.id == LLMModel.provider_id).where(LLMModel.id == model_id, LLMModel.status == LLMStatus.ACTIVE))).one_or_none()
    if model_row is None:
        return None, "Model not found or disabled."
    model, provider = model_row
    credential = (await db.execute(select(LLMProviderCredential).where(LLMProviderCredential.owner_id == owner_id, LLMProviderCredential.provider_id == provider.id))).scalar_one_or_none()
    if credential is None:
        return None, "No provider credential configured."
    try:
        api_key = decrypt_secret(credential.ciphertext)
        max_tokens = data.max_output_tokens or model.max_output_tokens or 512
        temperature = data.temperature if data.temperature is not None else 0.2
        if provider.api_family == "openai_compatible":
            urls = {"openai": "https://api.openai.com/v1/chat/completions", "groq": "https://api.groq.com/openai/v1/chat/completions", "nvidia": "https://integrate.api.nvidia.com/v1/chat/completions"}
            url = urls.get(provider.slug)
            if not url:
                return None, f"Completion is not configured for provider '{provider.slug}'."
            payload = {"model": model.model_name, "messages": ([{"role": "system", "content": data.system_prompt}] if data.system_prompt else []) + [{"role": "user", "content": data.prompt}], "temperature": temperature, "max_tokens": max_tokens}
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(url, headers={"Authorization": f"Bearer {api_key}"}, json=payload)
            if not response.is_success:
                return None, _provider_error(response)
            content = response.json().get("choices", [{}])[0].get("message", {}).get("content")
            return ((model_id, content), None) if isinstance(content, str) else (None, "Provider returned no text output.")
        if provider.slug == "anthropic":
            payload = {"model": model.model_name, "max_tokens": max_tokens, "temperature": temperature, "messages": [{"role": "user", "content": data.prompt}]}
            if data.system_prompt:
                payload["system"] = data.system_prompt
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"}, json=payload)
            if not response.is_success:
                return None, _provider_error(response)
            content = response.json().get("content", [{}])[0].get("text")
            return ((model_id, content), None) if isinstance(content, str) else (None, "Provider returned no text output.")
        if provider.slug == "google":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model.model_name}:generateContent?key={api_key}"
            payload = {"contents": [{"parts": [{"text": f"{data.system_prompt}\n\n{data.prompt}" if data.system_prompt else data.prompt}]}], "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}}
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(url, json=payload)
            if not response.is_success:
                return None, _provider_error(response)
            content = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text")
            return ((model_id, content), None) if isinstance(content, str) else (None, "Provider returned no text output.")
        return None, f"Completion is not configured for provider '{provider.slug}'."
    except InvalidToken:
        return None, "Stored credential cannot be decrypted; save the provider key again."
    except httpx.TimeoutException:
        return None, "Provider request timed out."
    except httpx.HTTPError as exc:
        return None, f"Provider request failed: {type(exc).__name__}."

async def save_credential(db, owner_id: int, provider_id: int, api_key: str):
    credential = (await db.execute(select(LLMProviderCredential).where(LLMProviderCredential.owner_id == owner_id, LLMProviderCredential.provider_id == provider_id))).scalar_one_or_none()
    if credential is None:
        credential = LLMProviderCredential(owner_id=owner_id, provider_id=provider_id, ciphertext=encrypt_secret(api_key), status=CredentialStatus.UNKNOWN)
        db.add(credential)
    else:
        credential.ciphertext = encrypt_secret(api_key)
        credential.status = CredentialStatus.UNKNOWN
    await db.commit()
    await db.refresh(credential)
    return credential
