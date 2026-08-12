"""结构化文档抽取中心 API。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.utils.auth_middleware import get_db, get_required_user
from yuxi.repositories.enterprise_repository import EnterpriseRepository
from yuxi.services.enterprise_extraction_service import (
    cancel_batch,
    create_batch,
    create_batch_from_uploads,
    create_template,
    export_batch,
    rerun_batch,
    revise_task,
    validate_template_schema,
)
from yuxi.storage.postgres.models_business import User
from yuxi.storage.postgres.models_enterprise import ExtractionTemplate
from yuxi.permissions import ResourcePermission

from server.utils.knowledge_permissions import ensure_knowledge_base_permission

extraction_router = APIRouter(prefix="/extraction", tags=["extraction"])


class TemplatePayload(BaseModel):
    """抽取模板写入参数。"""

    name: str = Field(min_length=1, max_length=255)
    schema_json: dict[str, Any]
    field_descriptions: dict[str, Any] = Field(default_factory=dict)
    required_fields: list[str] = Field(default_factory=list)
    prompt: str = ""
    version: int = Field(default=1, ge=1)
    is_active: bool = True


class BatchPayload(BaseModel):
    """抽取批次创建参数。"""

    template_id: str
    file_ids: list[str] = Field(min_length=1)
    model_spec: str | None = None


class RevisionPayload(BaseModel):
    """人工校对结果。"""

    result_json: dict[str, Any]
    evidence: list[dict[str, Any]] = Field(default_factory=list)


def _raise_validation(exc: ValueError) -> None:
    detail = exc.args[0] if exc.args else str(exc)
    raise HTTPException(status_code=422, detail=detail) from exc


@extraction_router.get("/templates")
async def list_templates(current_user: User = Depends(get_required_user), db: AsyncSession = Depends(get_db)):
    templates = await EnterpriseRepository(db).list_templates(str(current_user.uid))
    return {"templates": [template.to_dict() for template in templates]}


@extraction_router.post("/templates")
async def create_template_route(
    payload: TemplatePayload,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        template = await create_template(db, str(current_user.uid), payload.model_dump())
    except ValueError as exc:
        _raise_validation(exc)
    return {"template": template.to_dict()}


@extraction_router.get("/templates/{template_id}")
async def get_template(
    template_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    template = await EnterpriseRepository(db).get_template(template_id, str(current_user.uid))
    if not template:
        raise HTTPException(status_code=404, detail="抽取模板不存在")
    return {"template": template.to_dict()}


@extraction_router.put("/templates/{template_id}")
async def update_template(
    template_id: str,
    payload: TemplatePayload,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    template = await EnterpriseRepository(db).get_template(template_id, str(current_user.uid))
    if not template:
        raise HTTPException(status_code=404, detail="抽取模板不存在")
    try:
        required_fields = payload.required_fields or payload.schema_json.get("required") or []
        validate_template_schema(payload.schema_json, required_fields)
    except ValueError as exc:
        _raise_validation(exc)
    if not payload.name.strip():
        raise HTTPException(status_code=422, detail="模板名称不能为空")
    schema_json = dict(payload.schema_json)
    if required_fields:
        schema_json["required"] = required_fields
    duplicate_result = await db.execute(
        select(ExtractionTemplate.id).where(
            ExtractionTemplate.owner_uid == str(current_user.uid),
            ExtractionTemplate.name == payload.name.strip(),
            ExtractionTemplate.version == payload.version,
            ExtractionTemplate.id != template.id,
        )
    )
    if duplicate_result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="同名同版本模板已存在")
    template.name = payload.name.strip()
    template.schema_json = schema_json
    template.field_descriptions = payload.field_descriptions
    template.required_fields = required_fields
    template.prompt = payload.prompt.strip()
    template.version = payload.version
    template.is_active = payload.is_active
    return {"template": template.to_dict()}


@extraction_router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    template = await EnterpriseRepository(db).get_template(template_id, str(current_user.uid))
    if not template:
        raise HTTPException(status_code=404, detail="抽取模板不存在")
    # 模板可能已被批次引用，停用可以保留历史结果和版本证据。
    template.is_active = False
    return {"success": True, "template": template.to_dict()}


@extraction_router.get("/batches")
async def list_batches(current_user: User = Depends(get_required_user), db: AsyncSession = Depends(get_db)):
    batches = await EnterpriseRepository(db).list_batches(str(current_user.uid))
    return {"batches": [batch.to_dict() for batch in batches]}


@extraction_router.post("/batches")
async def create_batch_route(
    payload: BatchPayload,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        batch = await create_batch(db, str(current_user.uid), payload.model_dump(), current_user=current_user)
    except ValueError as exc:
        _raise_validation(exc)
    return {"batch": batch.to_dict()}


@extraction_router.post("/batches/upload")
async def create_upload_batch_route(
    template_id: str = Form(...),
    kb_id: str = Form(...),
    model_spec: str | None = Form(None),
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_knowledge_base_permission(kb_id, current_user, ResourcePermission.MANAGE)
    try:
        batch = await create_batch_from_uploads(
            db,
            str(current_user.uid),
            template_id,
            kb_id,
            files,
            model_spec,
            current_user,
        )
    except ValueError as exc:
        _raise_validation(exc)
    return {"batch": batch.to_dict()}


@extraction_router.get("/batches/{batch_id}")
async def get_batch(
    batch_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    repo = EnterpriseRepository(db)
    batch = await repo.get_batch(batch_id, str(current_user.uid))
    if not batch:
        raise HTTPException(status_code=404, detail="抽取批次不存在")
    tasks = await repo.list_extraction_tasks(batch.id, str(current_user.uid))
    return {"batch": batch.to_dict(), "tasks": [task.to_dict() for task in tasks]}


@extraction_router.post("/batches/{batch_id}/rerun")
async def rerun_batch_route(
    batch_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    batch = await EnterpriseRepository(db).get_batch(batch_id, str(current_user.uid))
    if not batch:
        raise HTTPException(status_code=404, detail="抽取批次不存在")
    try:
        task_ids = await rerun_batch(db, batch, str(current_user.uid))
    except ValueError as exc:
        _raise_validation(exc)
    return {"batch": batch.to_dict(), "task_ids": task_ids}


@extraction_router.post("/batches/{batch_id}/cancel")
async def cancel_batch_route(
    batch_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    batch = await EnterpriseRepository(db).get_batch(batch_id, str(current_user.uid))
    if not batch:
        raise HTTPException(status_code=404, detail="抽取批次不存在")
    try:
        task_ids = await cancel_batch(db, batch, str(current_user.uid))
    except ValueError as exc:
        _raise_validation(exc)
    return {"batch": batch.to_dict(), "task_ids": task_ids}


@extraction_router.get("/batches/{batch_id}/export")
async def export_batch_route(
    batch_id: str,
    format_name: str = Query("json", alias="format"),
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    batch = await EnterpriseRepository(db).get_batch(batch_id, str(current_user.uid))
    if not batch:
        raise HTTPException(status_code=404, detail="抽取批次不存在")
    try:
        content, media_type = await export_batch(db, batch, str(current_user.uid), format_name)
    except ValueError as exc:
        _raise_validation(exc)
    extension = "csv" if format_name == "csv" else "json"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="extraction-{batch.id}.{extension}"'},
    )


@extraction_router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    repo = EnterpriseRepository(db)
    task = await repo.get_extraction_task(task_id, str(current_user.uid))
    if not task:
        raise HTTPException(status_code=404, detail="抽取任务不存在")
    revisions = await repo.list_revisions(task.id, str(current_user.uid))
    return {"task": task.to_dict(), "revisions": [revision.to_dict() for revision in revisions]}


@extraction_router.post("/tasks/{task_id}/revise")
async def revise_task_route(
    task_id: str,
    payload: RevisionPayload,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    task = await EnterpriseRepository(db).get_extraction_task(task_id, str(current_user.uid))
    if not task:
        raise HTTPException(status_code=404, detail="抽取任务不存在")
    try:
        revision = await revise_task(
            db,
            task,
            str(current_user.uid),
            payload.result_json,
            payload.evidence,
        )
    except ValueError as exc:
        _raise_validation(exc)
    return {"task": task.to_dict(), "revision": revision.to_dict()}
