from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from agent_auth import CurrentUser
from sqlalchemy import select
from app.core.auth import current_user
from app.db.session import get_db
from app.models.llm import LLMModel, LLMProvider
from app.schemas.llm import CompletionRequest, CompletionResponse, ConnectionTestResponse, CredentialCreate, CredentialResponse, DefaultResponse, ModelAccessUpdate, ModelCreate, ModelResponse, ModelUpdate, ProviderResponse
from app.services.catalog import complete_model, create_model, delete_model, get_model, list_models, save_credential, seed_catalog, set_access, set_default, test_model_connection, update_model

router = APIRouter(tags=["LLM Models"])

async def _models(db, owner_id):
    rows = await list_models(db, owner_id)
    return [ModelResponse(id=model.id, provider_id=provider.id, provider_slug=provider.slug, model_name=model.model_name, display_name=model.display_name, capabilities=model.capabilities, context_window=model.context_window, max_output_tokens=model.max_output_tokens, status=model.status, enabled=bool(access and access.enabled), is_default=bool(access and access.is_default), test_status=access.last_test_status if access else "UNKNOWN", last_tested_at=access.last_tested_at if access else None, last_test_error=access.last_test_error if access else None) for model, provider, access in rows]

async def _model_response(db, owner_id: int, model_id: int) -> ModelResponse:
    model = next((item for item in await _models(db, owner_id) if item.id == model_id), None)
    if model is None:
        raise HTTPException(404, "Model not found")
    return model

@router.get("/providers", response_model=list[ProviderResponse])
async def providers(user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    await seed_catalog(db)
    return list((await db.execute(select(LLMProvider).order_by(LLMProvider.display_name))).scalars().all())

@router.get("/models", response_model=list[ModelResponse])
async def models(user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    await seed_catalog(db)
    return await _models(db, user.user_id)

@router.post("/models", response_model=ModelResponse, status_code=status.HTTP_201_CREATED)
async def create_llm_model(data: ModelCreate, user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    await seed_catalog(db)
    try:
        model = await create_model(db, data)
    except IntegrityError as error:
        raise HTTPException(409, "A model with this name already exists for the provider.") from error
    if model is None:
        raise HTTPException(404, "Provider not found")
    return await _model_response(db, user.user_id, model.id)

@router.get("/models/{model_id}", response_model=ModelResponse)
async def model_detail(model_id: int, user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    await seed_catalog(db)
    return await _model_response(db, user.user_id, model_id)

@router.patch("/models/{model_id}", response_model=ModelResponse)
async def update_llm_model(model_id: int, data: ModelUpdate, user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    await seed_catalog(db)
    model = await get_model(db, model_id)
    if model is None:
        raise HTTPException(404, "Model not found")
    try:
        await update_model(db, model, data)
    except IntegrityError as error:
        raise HTTPException(409, "A model with this name already exists for the provider.") from error
    return await _model_response(db, user.user_id, model_id)

@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_model(model_id: int, user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    await seed_catalog(db)
    if not await delete_model(db, model_id):
        raise HTTPException(404, "Model not found")

@router.post("/models/{model_id}/test", response_model=ConnectionTestResponse)
async def test_llm_model(model_id: int, user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    await seed_catalog(db)
    result = await test_model_connection(db, user.user_id, model_id)
    if result is None:
        raise HTTPException(404, "Model not found")
    tested_model_id, test_status, tested_at, error = result
    return ConnectionTestResponse(model_id=tested_model_id, status=test_status, tested_at=tested_at, error=error)

@router.post("/models/{model_id}/complete", response_model=CompletionResponse)
async def complete_llm_model(model_id: int, data: CompletionRequest, user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    await seed_catalog(db)
    try:
        completion, error = await complete_model(db, user.user_id, model_id, data)
    except Exception as exc:
        await db.rollback()
        raise HTTPException(502, f"LLM completion failed: {type(exc).__name__}") from exc
    if completion is None:
        raise HTTPException(400, error or "LLM completion failed")
    completed_model_id, output = completion
    if not isinstance(output, str):
        raise HTTPException(502, "LLM provider returned an invalid text response.")
    return CompletionResponse(model_id=completed_model_id, output=output)

@router.post("/models/{model_id}/access", response_model=ModelResponse)
async def model_access(model_id: int, data: ModelAccessUpdate, user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    await seed_catalog(db)
    model = (await db.execute(select(LLMModel).where(LLMModel.id == model_id))).scalar_one_or_none()
    if not model:
        raise HTTPException(404, "Model not found")
    await set_access(db, user.user_id, model_id, data.enabled)
    return await _model_response(db, user.user_id, model_id)

@router.put("/models/{model_id}/default", response_model=DefaultResponse)
async def default_model(model_id: int, user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    await seed_catalog(db)
    await set_default(db, user.user_id, model_id)
    return DefaultResponse(model_id=model_id)

@router.get("/defaults", response_model=DefaultResponse)
async def defaults(user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    from app.models.llm import LLMModelAccess
    access = (await db.execute(select(LLMModelAccess).where(LLMModelAccess.owner_id == user.user_id, LLMModelAccess.is_default.is_(True)))).scalar_one_or_none()
    return DefaultResponse(model_id=access.model_id if access else None)

@router.post("/providers/{provider_id}/credentials", response_model=CredentialResponse)
async def credentials(provider_id: int, data: CredentialCreate, user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    provider = (await db.execute(select(LLMProvider).where(LLMProvider.id == provider_id))).scalar_one_or_none()
    if not provider:
        raise HTTPException(404, "Provider not found")
    credential = await save_credential(db, user.user_id, provider_id, data.api_key)
    return CredentialResponse(provider_id=provider_id, status=credential.status, configured=True, updated_at=credential.updated_at)
