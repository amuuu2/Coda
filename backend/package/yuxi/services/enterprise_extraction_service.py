"""结构化文档抽取：解析、LLM JSON 输出校验、证据和人工修订。"""

from __future__ import annotations

import csv
import io
import json
import os
import uuid
from collections import Counter
from typing import Any

from jsonschema import Draft202012Validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.knowledge.parser.unified import parse_resolved_document
from yuxi.knowledge.parser.unified import is_supported_file_extension
from yuxi.repositories.enterprise_repository import EnterpriseRepository
from yuxi.storage.postgres.models_enterprise import (
    ExtractionBatch,
    ExtractionResultRevision,
    ExtractionTask,
    ExtractionTemplate,
)
from yuxi.utils.datetime_utils import utc_now_naive

EXTRACTION_TERMINAL_STATUSES = {"success", "failed", "cancelled"}


def validate_template_schema(schema_json: dict, required_fields: list[str]) -> None:
    """校验 JSON Schema 本身以及模板必填字段声明。"""
    if not isinstance(schema_json, dict) or schema_json.get("type") not in {None, "object"}:
        raise ValueError("抽取模板 JSON Schema 必须是对象 Schema")
    try:
        Draft202012Validator.check_schema(schema_json)
    except Exception as exc:
        raise ValueError(f"JSON Schema 无效: {exc}") from exc
    properties = schema_json.get("properties") or {}
    invalid_required = [field for field in required_fields if field not in properties]
    if invalid_required:
        raise ValueError(f"必填字段不在 properties 中: {', '.join(invalid_required)}")


def validate_extraction_result(schema_json: dict, result: object) -> list[dict[str, Any]]:
    """使用 JSON Schema 校验模型输出，返回可读错误而不是吞掉失败。"""
    errors = []
    for error in Draft202012Validator(schema_json).iter_errors(result):
        path = ".".join(str(item) for item in error.absolute_path) or "$"
        errors.append({"path": path, "message": error.message, "validator": error.validator})
    return errors


def _response_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(item.get("text", "") for item in content if isinstance(item, dict))
    return str(content)


def _parse_json_response(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
        cleaned = cleaned.rsplit("```", 1)[0].strip()
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise ValueError("抽取模型必须返回 JSON 对象")
    return value


def _normalize_evidence(raw: dict) -> list[dict[str, Any]]:
    evidence = raw.get("_evidence")
    if isinstance(evidence, list):
        return [item for item in evidence if isinstance(item, dict)]
    return [{"field": "$", "locatable": False, "reason": "模型未返回文件、页码或段落证据"}]


async def create_template(db: AsyncSession, owner_uid: str, data: dict) -> ExtractionTemplate:
    """创建一份版本化抽取模板。"""
    schema_json = dict(data.get("schema_json") or {})
    required_fields = list(data.get("required_fields") or schema_json.get("required") or [])
    validate_template_schema(schema_json, required_fields)
    if required_fields:
        schema_json["required"] = required_fields
    name = str(data.get("name") or "").strip()
    if not name:
        raise ValueError("模板名称不能为空")
    version = int(data.get("version") or 1)
    existing_result = await db.execute(
        select(ExtractionTemplate.id).where(
            ExtractionTemplate.owner_uid == str(owner_uid),
            ExtractionTemplate.name == name,
            ExtractionTemplate.version == version,
        )
    )
    if existing_result.scalar_one_or_none():
        raise ValueError("同名同版本模板已存在")
    result = ExtractionTemplate(
        id=str(uuid.uuid4()),
        owner_uid=str(owner_uid),
        name=name,
        schema_json=schema_json,
        field_descriptions=dict(data.get("field_descriptions") or {}),
        required_fields=required_fields,
        prompt=str(data.get("prompt") or "").strip(),
        version=version,
        is_active=bool(data.get("is_active", True)),
    )
    db.add(result)
    await db.flush()
    return result


async def create_batch(
    db: AsyncSession,
    owner_uid: str,
    data: dict,
    *,
    current_user: Any | None = None,
) -> ExtractionBatch:
    """为用户可见的知识文件创建批量抽取任务并投递 worker。"""
    repo = EnterpriseRepository(db)
    template = await repo.get_template(str(data.get("template_id")), owner_uid)
    if not template or not template.is_active:
        raise ValueError("抽取模板不存在或已停用")

    file_ids = [str(file_id).strip() for file_id in data.get("file_ids") or [] if str(file_id).strip()]
    if not file_ids:
        raise ValueError("至少选择一个知识文件")
    if len(file_ids) != len(set(file_ids)):
        raise ValueError("同一知识文件不能在一个批次中重复选择")

    from yuxi.storage.postgres.models_knowledge import KnowledgeFile

    files_result = await db.execute(select(KnowledgeFile).where(KnowledgeFile.file_id.in_(file_ids)))
    files = {file.file_id: file for file in files_result.scalars().all()}
    if len(files) != len(set(file_ids)):
        raise ValueError("只能选择当前可访问且存在的知识文件")

    if current_user is None:
        if any(file.created_by != str(owner_uid) for file in files.values()):
            raise ValueError("只能选择当前用户创建且存在的知识文件")
    else:
        from yuxi.knowledge.runtime import knowledge_base
        from yuxi.permissions import ResourcePermission, ResourcePermissionDenied, require_knowledge_base_permission

        for kb_id in {file.kb_id for file in files.values()}:
            db_info = await knowledge_base.get_database_info(kb_id)
            if not db_info:
                raise ValueError("知识库不存在")
            try:
                require_knowledge_base_permission(current_user, db_info, ResourcePermission.READ)
            except ResourcePermissionDenied as exc:
                raise ValueError("无权读取所选知识文件") from exc

    batch = ExtractionBatch(
        id=str(uuid.uuid4()),
        owner_uid=str(owner_uid),
        template_id=template.id,
        template_version=template.version,
        template_schema_json=template.schema_json or {},
        template_field_descriptions=template.field_descriptions or {},
        template_required_fields=template.required_fields or [],
        template_prompt=template.prompt or "",
        model_spec=data.get("model_spec"),
        total_count=len(file_ids),
        queued_count=len(file_ids),
    )
    db.add(batch)
    tasks = []
    for file_id in file_ids:
        file = files[file_id]
        tasks.append(
            ExtractionTask(
                id=str(uuid.uuid4()),
                batch_id=batch.id,
                owner_uid=str(owner_uid),
                file_id=file.file_id,
                filename=file.filename,
            )
        )
    db.add_all(tasks)
    await db.commit()

    from yuxi.services.run_queue_service import get_arq_pool

    queue = await get_arq_pool()
    for task in tasks:
        await queue.enqueue_job("process_extraction_task", task.id, _job_id=f"extract:{task.id}")
    return batch


async def create_batch_from_uploads(
    db: AsyncSession,
    owner_uid: str,
    template_id: str,
    kb_id: str,
    files: list[Any],
    model_spec: str | None = None,
    current_user: Any | None = None,
) -> ExtractionBatch:
    """把批量上传文件写入现有知识库后创建抽取批次。"""
    repo = EnterpriseRepository(db)
    template = await repo.get_template(template_id, owner_uid)
    if not template or not template.is_active:
        raise ValueError("抽取模板不存在或已停用")
    if not files:
        raise ValueError("至少上传一个文档")

    from yuxi.knowledge.runtime import knowledge_base
    from yuxi.knowledge.utils import calculate_content_hash
    from yuxi.storage.minio.client import MinIOClient, aupload_file_to_minio
    from yuxi.utils.upload_utils import MAX_UPLOAD_SIZE_BYTES, read_upload_with_limit

    _, supports_documents = await knowledge_base.get_database_document_support(kb_id)
    if not supports_documents:
        raise ValueError("所选知识库不支持文档上传")

    file_ids = []
    for upload in files:
        filename = os.path.basename(str(getattr(upload, "filename", "") or "")).strip()
        if not filename:
            raise ValueError("上传文件必须包含文件名")
        if not is_supported_file_extension(filename):
            raise ValueError(f"不支持的文件类型: {os.path.splitext(filename)[1].lower()}")

        file_bytes = await read_upload_with_limit(
            upload,
            max_size_bytes=MAX_UPLOAD_SIZE_BYTES,
            too_large_message="文件过大，当前仅支持 100 MB 以内的文件",
        )
        content_hash = await calculate_content_hash(file_bytes)
        if await knowledge_base.file_existed_in_db(kb_id, content_hash):
            raise ValueError(f"知识库中已存在相同内容文件: {filename}")

        stem, suffix = os.path.splitext(filename)
        storage_filename = f"{stem}_{uuid.uuid4().hex}{suffix.lower()}"
        object_name = f"{kb_id}/upload/{storage_filename}"
        minio_url = await aupload_file_to_minio(
            MinIOClient.KB_BUCKETS["documents"],
            object_name,
            file_bytes,
        )
        metadata = await knowledge_base.add_file_record(
            kb_id,
            minio_url,
            params={
                "content_type": "file",
                "content_hashes": {minio_url: content_hash},
                "file_sizes": {minio_url: len(file_bytes)},
                "source_paths": {minio_url: filename},
            },
            operator_id=owner_uid,
        )
        file_ids.append(metadata["file_id"])

    return await create_batch(
        db,
        owner_uid,
        {"template_id": template_id, "file_ids": file_ids, "model_spec": model_spec},
        current_user=current_user,
    )


async def rerun_batch(db: AsyncSession, batch: ExtractionBatch, owner_uid: str) -> list[str]:
    """将失败或已完成任务重新置为排队，并按任务幂等投递。"""
    repo = EnterpriseRepository(db)
    tasks = await repo.list_extraction_tasks(batch.id, owner_uid)
    task_ids = []
    for task in tasks:
        if task.status == "processing":
            continue
        task.status = "queued"
        task.error_message = None
        task.validation_errors = []
        task.attempt = 0
        task_ids.append(task.id)
    batch.status = "queued"
    await _refresh_batch_counts(db, batch)
    await db.commit()

    from yuxi.services.run_queue_service import get_arq_pool

    queue = await get_arq_pool()
    for task_id in task_ids:
        await queue.enqueue_job("process_extraction_task", task_id, _job_id=f"extract:{task_id}:{uuid.uuid4()}")
    return task_ids


async def cancel_batch(db: AsyncSession, batch: ExtractionBatch, owner_uid: str) -> list[str]:
    """取消尚未开始执行的抽取任务，并刷新批次状态。"""
    tasks = await EnterpriseRepository(db).list_extraction_tasks(batch.id, owner_uid)
    cancelled_ids = []
    for task in tasks:
        if task.status == "queued":
            task.status = "cancelled"
            task.error_message = "用户取消抽取任务"
            cancelled_ids.append(task.id)
    await _refresh_batch_counts(db, batch)
    return cancelled_ids


async def revise_task(
    db: AsyncSession,
    task: ExtractionTask,
    owner_uid: str,
    result_json: dict,
    evidence: list[dict],
) -> ExtractionResultRevision:
    """保存人工修订，并将任务当前结果更新为修订版本。"""
    batch_result = await db.execute(select(ExtractionBatch).where(ExtractionBatch.id == task.batch_id))
    batch = batch_result.scalar_one_or_none()
    if not batch or batch.owner_uid != str(owner_uid):
        raise ValueError("抽取任务不存在")
    template_result = await db.execute(select(ExtractionTemplate).where(ExtractionTemplate.id == batch.template_id))
    template = template_result.scalar_one_or_none()
    if not template:
        raise ValueError("抽取模板不存在")
    errors = validate_extraction_result(getattr(batch, "template_schema_json", None) or template.schema_json, result_json)
    if errors:
        raise ValueError({"message": "人工修订结果不符合 JSON Schema", "errors": errors})

    revisions_result = await db.execute(
        select(ExtractionResultRevision.revision_no)
        .where(ExtractionResultRevision.task_id == task.id)
        .order_by(ExtractionResultRevision.revision_no.desc())
        .limit(1)
    )
    latest = revisions_result.scalar_one_or_none() or 0
    revision = ExtractionResultRevision(
        id=str(uuid.uuid4()),
        task_id=task.id,
        owner_uid=str(owner_uid),
        revision_no=int(latest) + 1,
        revision_type="manual",
        result_json=result_json,
        evidence=evidence,
        revised_by_uid=str(owner_uid),
    )
    task.extracted_result = result_json
    task.evidence = evidence
    task.validation_errors = []
    task.status = "success"
    db.add(revision)
    await db.flush()
    return revision


async def process_extraction_task(ctx, task_id: str) -> None:
    """由现有 ARQ worker 执行单个文档抽取任务。"""
    from yuxi.storage.postgres.manager import pg_manager

    retry_error: Exception | None = None
    async with pg_manager.get_async_session_context() as db:
        task_result = await db.execute(select(ExtractionTask).where(ExtractionTask.id == task_id).with_for_update())
        task = task_result.scalar_one_or_none()
        if not task or task.status in EXTRACTION_TERMINAL_STATUSES:
            return

        batch_result = await db.execute(select(ExtractionBatch).where(ExtractionBatch.id == task.batch_id))
        batch = batch_result.scalar_one_or_none()
        if not batch:
            raise ValueError("抽取批次不存在")
        template_result = await db.execute(select(ExtractionTemplate).where(ExtractionTemplate.id == batch.template_id))
        template = template_result.scalar_one_or_none()
        if not template:
            raise ValueError("抽取模板不存在")

        task.status = "parsing"
        task.attempt += 1
        task.started_at = utc_now_naive()
        from yuxi.storage.postgres.models_knowledge import KnowledgeFile

        file_result = await db.execute(select(KnowledgeFile).where(KnowledgeFile.file_id == task.file_id))
        source_file = file_result.scalar_one_or_none()
        if not source_file:
            task.status = "failed"
            task.error_message = "知识文件不存在"
            task.finished_at = utc_now_naive()
            await _refresh_batch_counts(db, batch)
            return

        source = source_file.minio_url or source_file.markdown_file or source_file.path
        if not source:
            task.status = "failed"
            task.error_message = "知识文件没有可解析的对象地址"
            task.finished_at = utc_now_naive()
            await _refresh_batch_counts(db, batch)
            return

        try:
            markdown = (await parse_resolved_document(source, params=source_file.processing_params or {})).markdown
            task.status = "extracting"
            from yuxi.agents.models import load_chat_model

            model = load_chat_model(batch.model_spec)
            prompt = (
                "只返回一个 JSON 对象，不要 Markdown 代码围栏。\n"
                f"JSON Schema:\n{json.dumps(getattr(batch, 'template_schema_json', None) or template.schema_json, ensure_ascii=False)}\n"
                f"字段说明:\n{json.dumps(getattr(batch, 'template_field_descriptions', None) or template.field_descriptions or {}, ensure_ascii=False)}\n"
                f"抽取要求:\n{getattr(batch, 'template_prompt', None) or template.prompt}\n"
                "如无法定位原文，不要猜测页码；可将证据放入 `_evidence` 数组。\n"
                f"文档内容:\n{markdown}"
            )
            response = await model.ainvoke(prompt)
            raw_result = _parse_json_response(_response_text(response))
            task.raw_result = raw_result
            task.status = "validating"
            result_json = {key: value for key, value in raw_result.items() if key != "_evidence"}
            validation_errors = validate_extraction_result(
                getattr(batch, "template_schema_json", None) or template.schema_json,
                result_json,
            )
            task.validation_errors = validation_errors
            task.evidence = _normalize_evidence(raw_result)
            if validation_errors:
                task.status = "failed"
                task.error_message = "模型输出未通过 JSON Schema 校验"
                raise ValueError(task.error_message)

            task.extracted_result = result_json
            task.status = "success"
            revision_result = await db.execute(
                select(func.coalesce(func.max(ExtractionResultRevision.revision_no), 0)).where(
                    ExtractionResultRevision.task_id == task.id
                )
            )
            revision_no = int(revision_result.scalar_one()) + 1
            db.add(
                ExtractionResultRevision(
                    id=str(uuid.uuid4()),
                    task_id=task.id,
                    owner_uid=task.owner_uid,
                    revision_no=revision_no,
                    revision_type="model",
                    result_json=result_json,
                    evidence=task.evidence,
                )
            )
        except Exception as exc:
            task.status = "failed"
            task.error_message = str(exc)
            if _job_try(ctx) < 2:
                task.status = "queued"
                retry_error = exc
        finally:
            task.finished_at = utc_now_naive()
            await _refresh_batch_counts(db, batch)
            if retry_error is not None:
                # 先持久化 attempt 和 queued 状态，再把异常交给 ARQ 触发重试。
                await db.commit()

    if retry_error is not None:
        raise retry_error


async def _refresh_batch_counts(db: AsyncSession, batch: ExtractionBatch) -> None:
    """按任务事实状态重算批次摘要。"""
    tasks_result = await db.execute(select(ExtractionTask.status).where(ExtractionTask.batch_id == batch.id))
    counts = Counter(row[0] for row in tasks_result.all())
    batch.total_count = sum(counts.values())
    batch.queued_count = counts.get("queued", 0)
    batch.processing_count = sum(counts.get(status, 0) for status in ("parsing", "extracting", "validating"))
    batch.succeeded_count = counts.get("success", 0)
    batch.failed_count = counts.get("failed", 0)
    batch.cancelled_count = counts.get("cancelled", 0)
    if batch.total_count and batch.succeeded_count + batch.failed_count + batch.cancelled_count == batch.total_count:
        if batch.cancelled_count == batch.total_count:
            batch.status = "cancelled"
        else:
            batch.status = "success" if not batch.failed_count and not batch.cancelled_count else "completed_with_errors"
    elif batch.processing_count:
        batch.status = "processing"
    else:
        batch.status = "queued"
    batch.updated_at = utc_now_naive()


def _job_try(ctx) -> int:
    """读取 ARQ 当前尝试次数，缺少上下文时按首次尝试处理。"""
    if isinstance(ctx, dict):
        try:
            return int(ctx.get("job_try") or 1)
        except (TypeError, ValueError):
            return 1
    return 1


async def export_batch(db: AsyncSession, batch: ExtractionBatch, owner_uid: str, format_name: str) -> tuple[bytes, str]:
    """导出批次结果为 JSON 或 CSV。"""
    tasks = await EnterpriseRepository(db).list_extraction_tasks(batch.id, owner_uid)
    rows = [
        {
            "task_id": task.id,
            "file_id": task.file_id,
            "filename": task.filename,
            "status": task.status,
            "result": task.extracted_result or {},
            "evidence": task.evidence or [],
            "validation_errors": task.validation_errors or [],
        }
        for task in tasks
    ]
    if format_name == "json":
        return json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8"), "application/json"
    if format_name != "csv":
        raise ValueError("只支持 json 或 csv 导出")
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["task_id", "file_id", "filename", "status", "result", "evidence", "validation_errors"],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({key: json.dumps(row[key], ensure_ascii=False) if isinstance(row[key], (dict, list)) else row[key] for key in writer.fieldnames})
    return output.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8"
