from __future__ import annotations

from types import SimpleNamespace

from yuxi.services import enterprise_analytics_service as svc


def test_new_engine_forwards_data_source_options(monkeypatch):
    """数据源连接选项应传给 SQLAlchemy，同时保留默认连接超时。"""
    captured = {}

    monkeypatch.setattr(svc, "_engine_url", lambda _source: "db-url")
    monkeypatch.setattr(
        svc,
        "create_engine",
        lambda url, **kwargs: captured.update(url=url, kwargs=kwargs) or object(),
    )

    source = SimpleNamespace(
        options={"sslmode": "require", "connect_timeout": 12},
    )
    svc._new_engine(source)

    assert captured["url"] == "db-url"
    assert captured["kwargs"]["connect_args"] == {"sslmode": "require", "connect_timeout": 12}

