"""结构化文档抽取规则测试。

当前电脑未运行这些测试；由目标部署电脑在依赖安装后执行。
"""

from __future__ import annotations

import pytest

from yuxi.services.enterprise_extraction_service import (
    _normalize_evidence,
    _parse_json_response,
    create_template,
    export_batch,
    revise_task,
    validate_extraction_result,
    validate_template_schema,
)


def test_validate_template_schema_checks_required_properties():
    with pytest.raises(ValueError, match="不在 properties"):
        validate_template_schema(
            {"type": "object", "properties": {"revenue": {"type": "number"}}},
            ["missing"],
        )


def test_validate_extraction_result_returns_field_errors():
    errors = validate_extraction_result(
        {"type": "object", "required": ["revenue"], "properties": {"revenue": {"type": "number"}}},
        {},
    )

    assert errors[0]["path"] == "$"
    assert errors[0]["validator"] == "required"


def test_parse_json_response_removes_code_fence_and_normalizes_missing_evidence():
    assert _parse_json_response('```json\n{"revenue": 12}\n```') == {"revenue": 12}
    assert _normalize_evidence({}) == [
        {"field": "$", "locatable": False, "reason": "模型未返回文件、页码或段落证据"}
    ]


@pytest.mark.asyncio
async def test_create_template_merges_declared_required_fields_into_schema():
    class Result:
        def scalar_one_or_none(self):
            return None

    class Database:
        def __init__(self):
            self.template = None

        async def execute(self, statement):
            del statement
            return Result()

        def add(self, template):
            self.template = template

        async def flush(self):
            return None

    database = Database()
    template = await create_template(
        database,
        "user-1",
        {
            "name": "经营指标",
            "schema_json": {"type": "object", "properties": {"revenue": {"type": "number"}}},
            "required_fields": ["revenue"],
        },
    )

    assert template is database.template
    assert template.schema_json["required"] == ["revenue"]


@pytest.mark.asyncio
async def test_manual_revision_clears_previous_validation_errors(monkeypatch):
    class FakeResult:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class FakeDatabase:
        def __init__(self):
            self.revision = None

        async def execute(self, statement):
            statement_text = str(statement)
            if "extraction_batches" in statement_text:
                return FakeResult(type("Batch", (), {"owner_uid": "user-1", "template_id": "template-1"})())
            if "extraction_templates" in statement_text:
                return FakeResult(type("Template", (), {"schema_json": {"type": "object"}})())
            return type("RevisionResult", (), {"scalar_one_or_none": lambda self: 0})()

        def add(self, revision):
            self.revision = revision

        async def flush(self):
            return None

    task = type(
        "Task",
        (),
        {
            "id": "task-1",
            "batch_id": "batch-1",
            "extracted_result": {"value": 1},
            "evidence": [],
            "validation_errors": [{"message": "old"}],
            "status": "failed",
        },
    )()
    database = FakeDatabase()

    monkeypatch.setattr(
        "yuxi.services.enterprise_extraction_service.validate_extraction_result",
        lambda schema, result: [],
    )

    revision = await revise_task(database, task, "user-1", {"value": 2}, [{"field": "value", "locatable": True}])

    assert task.status == "success"
    assert task.validation_errors == []
    assert revision.revision_type == "manual"


@pytest.mark.asyncio
async def test_export_batch_includes_validation_errors(monkeypatch):
    class FakeRepository:
        def __init__(self, db):
            del db

        async def list_extraction_tasks(self, batch_id, owner_uid):
            assert (batch_id, owner_uid) == ("batch-1", "user-1")
            return [
                type(
                    "Task",
                    (),
                    {
                        "id": "task-1",
                        "file_id": "file-1",
                        "filename": "report.pdf",
                        "status": "failed",
                        "extracted_result": None,
                        "evidence": [],
                        "validation_errors": [{"path": "revenue", "message": "required"}],
                    },
                )()
            ]

    monkeypatch.setattr(
        "yuxi.services.enterprise_extraction_service.EnterpriseRepository",
        FakeRepository,
    )
    content, media_type = await export_batch(object(), object(), "user-1", "csv")

    assert media_type.startswith("text/csv")
    assert b"validation_errors" in content
    assert b"required" in content
