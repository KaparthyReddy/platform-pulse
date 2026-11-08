from __future__ import annotations

from pulse import runbooks


def test_loads_all_runbooks():
    names = {rb.name for rb in runbooks.load_runbooks()}
    assert names == {
        "airflow-scheduler-lag",
        "flink-checkpoint-failures",
        "spark-executor-oom",
        "trino-query-queueing",
    }


def test_search_ranks_spark_oom_first():
    results = runbooks.search_runbooks("spark executor memory killed")
    assert results[0]["name"] == "spark-executor-oom"
    assert results[0]["score"] > 0


def test_search_ranks_flink_checkpoint_first():
    results = runbooks.search_runbooks("checkpoint timeout")
    assert results[0]["name"] == "flink-checkpoint-failures"


def test_search_service_filter():
    trino = runbooks.search_runbooks("query queued", service="trino")
    assert trino[0]["name"] == "trino-query-queueing"
    spark = runbooks.search_runbooks("query queued", service="spark")
    assert all("spark" in r["services"] for r in spark)


def test_search_limit():
    assert len(runbooks.search_runbooks("failure memory queued", limit=2)) <= 2


def test_empty_and_stopword_queries_return_nothing():
    assert runbooks.search_runbooks("") == []
    assert runbooks.search_runbooks("the and of") == []


def test_get_runbook_sections():
    detail = runbooks.get_runbook("spark-executor-oom")
    assert detail is not None
    assert "memoryOverhead" in detail["mitigation"]
    assert detail["diagnosis"]
    assert detail["escalation"]


def test_get_runbook_missing():
    assert runbooks.get_runbook("does-not-exist") is None


def test_custom_directory_parsing(tmp_path):
    (tmp_path / "custom.md").write_text(
        "# Custom Runbook\n\n"
        "Services: Alpha, Beta\n"
        "Keywords: widget broken\n\n"
        "## Symptoms\n- widget is broken\n\n"
        "## Diagnosis\n1. Look.\n\n"
        "## Mitigation\n1. Fix.\n\n"
        "## Escalation\nPage someone.\n",
        encoding="utf-8",
    )
    loaded = runbooks.load_runbooks(tmp_path)
    assert len(loaded) == 1
    assert loaded[0].title == "Custom Runbook"
    assert loaded[0].services == ("alpha", "beta")
    results = runbooks.search_runbooks("widget broken", service="beta", directory=tmp_path)
    assert results[0]["name"] == "custom"
    assert runbooks.search_runbooks("widget", service="gamma", directory=tmp_path) == []
