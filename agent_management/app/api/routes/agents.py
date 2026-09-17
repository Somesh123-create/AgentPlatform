import httpx
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from agent_auth import CurrentUser

from app.core.auth import current_user
from app.core.config import settings
from app.db.session import get_db
from app.schemas.agent import AgentDraftCreate, AgentDraftResponse, AgentDraftUpdate, AgentFileUpdate, AgentFolderCreate, ArtifactValidationResponse
from app.schemas.build import AgentBuildResponse
from app.services.build import AgentBuildService
from app.services.agent import AgentDraftService
from app.schemas.runtime import AgentTestRequest, AgentTestResponse
from app.services.runtime import test_agent
from app.repositories.build import AgentBuildRepository
from app.schemas.invocation import AgentInvocationRequest, AgentInvocationResponse
from app.services.invocation import invoke_build
from app.models.conversation import AgentConversation, AgentMessage, MessageRole
from app.repositories.conversation import ConversationRepository
from app.schemas.conversation import ChatRequest, ConversationCreate, ConversationResponse, MessageResponse

router = APIRouter(prefix="/agents", tags=["Agents"])
bearer_token = OAuth2PasswordBearer(tokenUrl=settings.auth_token_url)

async def _owned_agent(agent_id: int, user_id: int, db: AsyncSession):
    draft = await AgentDraftService(db).get(user_id, agent_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Agent draft not found")
    return draft


@router.post("", response_model=AgentDraftResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(data: AgentDraftCreate, user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    return await AgentDraftService(db).create(user.user_id, data)


@router.get("", response_model=list[AgentDraftResponse])
async def list_agents(user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    return await AgentDraftService(db).list(user.user_id)


@router.get("/{agent_id}", response_model=AgentDraftResponse)
async def get_agent(agent_id: int, user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    draft = await AgentDraftService(db).get(user.user_id, agent_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Agent draft not found")
    return draft


@router.patch("/{agent_id}", response_model=AgentDraftResponse)
async def update_agent(agent_id: int, data: AgentDraftUpdate, user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    if data.default_build_id is not None:
        build = await AgentBuildRepository(db).get_owned(data.default_build_id, agent_id, user.user_id)
        if not build or build.status.value != "SUCCEEDED":
            raise HTTPException(status_code=409, detail="Default build must be a successful build for this agent.")
    draft = await AgentDraftService(db).update(user.user_id, agent_id, data)
    if not draft:
        raise HTTPException(status_code=404, detail="Agent draft not found")
    return draft


@router.post("/{agent_id}/generate", response_model=AgentDraftResponse)
async def generate_agent(agent_id: int, user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    draft = await AgentDraftService(db).generate(user.user_id, agent_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Agent draft not found")
    return draft


@router.put("/{agent_id}/files", response_model=AgentDraftResponse)
async def update_agent_file(agent_id: int, data: AgentFileUpdate, user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    try:
        draft = await AgentDraftService(db).update_file(user.user_id, agent_id, data.path, data.content, data.revision)
    except ValueError as error:
        raise HTTPException(status_code=409 if "changed" in str(error) else 400, detail=str(error)) from error
    if not draft:
        raise HTTPException(status_code=404, detail="Agent draft not found")
    return draft


@router.post("/{agent_id}/folders", response_model=AgentDraftResponse)
async def create_agent_folder(agent_id: int, data: AgentFolderCreate, user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    try:
        draft = await AgentDraftService(db).create_folder(user.user_id, agent_id, data.path, data.revision)
    except ValueError as error:
        raise HTTPException(status_code=409 if "changed" in str(error) else 400, detail=str(error)) from error
    if not draft:
        raise HTTPException(status_code=404, detail="Agent draft not found")
    return draft

@router.get("/{agent_id}/export")
async def export_agent(agent_id: int, user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    draft = await AgentDraftService(db).get(user.user_id, agent_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Agent draft not found")
    if not draft.files:
        raise HTTPException(status_code=409, detail="Generate the agent before exporting it.")
    archive = AgentDraftService(db).export_zip(draft)
    filename = f"{''.join(character if character.isalnum() or character in '-_' else '_' for character in draft.name.lower()) or 'agent'}.zip"
    return StreamingResponse(archive, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{filename}"'})

@router.post("/{agent_id}/validate", response_model=ArtifactValidationResponse)
async def validate_agent(agent_id: int, user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    draft = await AgentDraftService(db).get(user.user_id, agent_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Agent draft not found")
    return AgentDraftService(db).validate_artifact(draft)

@router.post("/{agent_id}/build", response_model=AgentBuildResponse, status_code=status.HTTP_201_CREATED)
async def build_agent(agent_id: int, user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    draft = await AgentDraftService(db).get(user.user_id, agent_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Agent draft not found")
    if not draft.files:
        raise HTTPException(status_code=409, detail="Generate the agent before building it.")
    return await AgentBuildService(db).build(draft, user.user_id)

@router.get("/{agent_id}/builds", response_model=list[AgentBuildResponse])
async def list_agent_builds(agent_id: int, user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    draft = await AgentDraftService(db).get(user.user_id, agent_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Agent draft not found")
    return await AgentBuildService(db).list_for_agent(agent_id, user.user_id)

@router.post("/{agent_id}/builds/{build_id}/run", response_model=AgentInvocationResponse)
async def run_agent_build(agent_id: int, build_id: int, data: AgentInvocationRequest, user: Annotated[CurrentUser, Depends(current_user)], token: Annotated[str, Depends(bearer_token)], db: AsyncSession = Depends(get_db)):
    draft = await _owned_agent(agent_id, user.user_id, db)
    build = await AgentBuildRepository(db).get_owned(build_id, agent_id, user.user_id)
    if not build:
        raise HTTPException(status_code=404, detail="Agent build not found")
    if build.status.value != "SUCCEEDED":
        raise HTTPException(status_code=409, detail="Only a successful agent build can be run.")
    try:
        return await invoke_build(draft, build, data.prompt, token)
    except (OSError, ValueError, httpx.HTTPError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

@router.post("/{agent_id}/test", response_model=AgentTestResponse)
async def test_agent_route(agent_id: int, data: AgentTestRequest, user: Annotated[CurrentUser, Depends(current_user)], token: Annotated[str, Depends(bearer_token)], db: AsyncSession = Depends(get_db)):
    draft = await AgentDraftService(db).get(user.user_id, agent_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Agent draft not found")
    try:
        return await test_agent(draft, data.prompt, token)
    except (httpx.HTTPError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

@router.get("/{agent_id}/conversations", response_model=list[ConversationResponse])
async def list_conversations(agent_id: int, user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    await _owned_agent(agent_id, user.user_id, db)
    return await ConversationRepository(db).list_for_agent(agent_id, user.user_id)

@router.post("/{agent_id}/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(agent_id: int, data: ConversationCreate, user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    await _owned_agent(agent_id, user.user_id, db)
    return await ConversationRepository(db).create(AgentConversation(agent_id=agent_id, owner_id=user.user_id, title=data.title))

@router.get("/{agent_id}/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages(agent_id: int, conversation_id: int, user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    conversation = await ConversationRepository(db).get_agent(conversation_id, agent_id, user.user_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return await ConversationRepository(db).messages(conversation_id)

@router.post("/{agent_id}/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def chat(agent_id: int, conversation_id: int, data: ChatRequest, user: Annotated[CurrentUser, Depends(current_user)], token: Annotated[str, Depends(bearer_token)], db: AsyncSession = Depends(get_db)):
    draft = await _owned_agent(agent_id, user.user_id, db)
    repository = ConversationRepository(db)
    conversation = await repository.get_agent(conversation_id, agent_id, user.user_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    build = await AgentBuildRepository(db).get_owned(data.build_id, agent_id, user.user_id)
    if not build or build.status.value != "SUCCEEDED":
        raise HTTPException(status_code=409, detail="Select a successful agent build before chatting.")
    await repository.add_message(AgentMessage(conversation_id=conversation_id, role=MessageRole.USER, content=data.prompt))
    try:
        result = await invoke_build(draft, build, data.prompt, token)
        await repository.add_message(AgentMessage(conversation_id=conversation_id, role=MessageRole.ASSISTANT, content=result["output"]))
    except (httpx.HTTPError, ValueError) as error:
        await repository.add_message(AgentMessage(conversation_id=conversation_id, role=MessageRole.ASSISTANT, content=f"Error: {error}"))
        return await repository.messages(conversation_id)
    return await repository.messages(conversation_id)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(agent_id: int, user: Annotated[CurrentUser, Depends(current_user)], db: AsyncSession = Depends(get_db)):
    if not await AgentDraftService(db).delete(user.user_id, agent_id):
        raise HTTPException(status_code=404, detail="Agent draft not found")
