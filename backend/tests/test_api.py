"""Integration tests for API endpoints."""
import json
import io
import pytest
import pytest_asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_taxonomy(client, name="Test Taxonomy"):
    resp = await client.post("/taxonomies", json={"name": name, "description": "desc"})
    assert resp.status_code == 200
    return resp.json()


async def _add_categories(client, taxonomy_id):
    cats = [
        {"name": "Greeting", "description": "Greetings"},
        {"name": "Complaint", "description": "Complaints"},
        {"name": "Technical Problem", "description": "Technical issues"},
    ]
    created = []
    for c in cats:
        resp = await client.post(f"/taxonomies/{taxonomy_id}/categories", json=c)
        assert resp.status_code == 200
        created.append(resp.json())
    return created


async def _upload_csv(client, name="Test DS"):
    csv_content = (
        "conversation_id,turn_index,speaker,text\n"
        "c1,0,customer,Hello I need help\n"
        "c1,1,agent,Sure how can I help\n"
        "c2,0,customer,Your service is terrible\n"
        "c2,1,agent,I am sorry to hear that\n"
    )
    files = {"file": ("test.csv", csv_content.encode(), "text/csv")}
    data = {"name": name, "description": "test dataset"}
    resp = await client.post("/datasets/upload", files=files, data=data)
    assert resp.status_code == 200
    return resp.json()


async def _upload_jsonl(client, name="JSONL DS"):
    conv = {
        "conversation_id": "jsonl-c1",
        "turns": [
            {"turn_index": 0, "role": "user", "content_text": "I need billing help"},
            {"turn_index": 1, "role": "assistant", "content_text": "Sure, let me check your account"},
        ],
    }
    content = json.dumps(conv) + "\n"
    files = {"file": ("test.jsonl", content.encode(), "application/jsonl")}
    data = {"name": name}
    resp = await client.post("/datasets/upload", files=files, data=data)
    assert resp.status_code == 200
    return resp.json()


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_datasets_empty(client):
    resp = await client.get("/datasets")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Taxonomies
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_taxonomy(client):
    tax = await _create_taxonomy(client)
    assert tax["name"] == "Test Taxonomy"
    assert tax["id"] > 0


@pytest.mark.asyncio
async def test_list_taxonomies(client):
    await _create_taxonomy(client, "T1")
    await _create_taxonomy(client, "T2")
    resp = await client.get("/taxonomies")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_get_taxonomy_detail(client):
    tax = await _create_taxonomy(client)
    await _add_categories(client, tax["id"])
    resp = await client.get(f"/taxonomies/{tax['id']}")
    assert resp.status_code == 200
    detail = resp.json()
    assert len(detail["categories"]) == 3


@pytest.mark.asyncio
async def test_taxonomy_not_found(client):
    resp = await client.get("/taxonomies/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_taxonomy(client):
    tax = await _create_taxonomy(client)
    resp = await client.put(f"/taxonomies/{tax['id']}", json={"name": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"


@pytest.mark.asyncio
async def test_delete_taxonomy(client):
    tax = await _create_taxonomy(client)
    resp = await client.delete(f"/taxonomies/{tax['id']}")
    assert resp.status_code == 200
    resp = await client.get(f"/taxonomies/{tax['id']}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_taxonomy_empty_name_rejected(client):
    resp = await client.post("/taxonomies", json={"name": "   "})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_category(client):
    tax = await _create_taxonomy(client)
    resp = await client.post(
        f"/taxonomies/{tax['id']}/categories",
        json={"name": "Intent A", "description": "Desc"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "INTENT_A"  # root categories are UPPER_CASE


@pytest.mark.asyncio
async def test_category_empty_name_rejected(client):
    tax = await _create_taxonomy(client)
    resp = await client.post(
        f"/taxonomies/{tax['id']}/categories",
        json={"name": "", "description": "Desc"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_category(client):
    tax = await _create_taxonomy(client)
    cats = await _add_categories(client, tax["id"])
    cat_id = cats[0]["id"]
    resp = await client.delete(f"/taxonomies/{tax['id']}/categories/{cat_id}")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_csv_dataset(client):
    ds = await _upload_csv(client)
    assert ds["name"] == "Test DS"
    assert ds["row_count"] == 4
    assert ds["file_type"] == "csv"


@pytest.mark.asyncio
async def test_upload_jsonl_dataset(client):
    ds = await _upload_jsonl(client)
    assert ds["name"] == "JSONL DS"
    assert ds["row_count"] == 2
    assert ds["file_type"] == "jsonl"


@pytest.mark.asyncio
async def test_list_datasets(client):
    await _upload_csv(client, "DS1")
    await _upload_csv(client, "DS2")
    resp = await client.get("/datasets")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_get_dataset(client):
    ds = await _upload_csv(client)
    resp = await client.get(f"/datasets/{ds['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test DS"


@pytest.mark.asyncio
async def test_dataset_not_found(client):
    resp = await client.get("/datasets/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_conversations(client):
    ds = await _upload_csv(client)
    resp = await client.get(f"/datasets/{ds['id']}/conversations")
    assert resp.status_code == 200
    convs = resp.json()
    assert len(convs) == 2


@pytest.mark.asyncio
async def test_get_conversation_detail(client):
    ds = await _upload_csv(client)
    resp = await client.get(f"/datasets/{ds['id']}/conversations")
    conv_id = resp.json()[0]["id"]
    resp = await client.get(f"/datasets/{ds['id']}/conversations/{conv_id}")
    assert resp.status_code == 200
    assert len(resp.json()["turns"]) == 2


@pytest.mark.asyncio
async def test_delete_dataset(client):
    ds = await _upload_csv(client)
    resp = await client.delete(f"/datasets/{ds['id']}")
    assert resp.status_code == 200
    resp = await client.get(f"/datasets/{ds['id']}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_unsupported_file(client):
    files = {"file": ("test.txt", b"hello", "text/plain")}
    resp = await client.post("/datasets/upload", files=files, data={"name": "bad"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_invalid_csv(client):
    csv_content = "conversation_id,turn_index,speaker,text\nc1,0,user,\n"
    files = {"file": ("test.csv", csv_content.encode(), "text/csv")}
    resp = await client.post("/datasets/upload", files=files, data={"name": "bad"})
    assert resp.status_code == 400
    assert "empty text" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classify_rule_based(client):
    ds = await _upload_csv(client)
    tax = await _create_taxonomy(client)
    await _add_categories(client, tax["id"])
    resp = await client.post("/classify", json={
        "dataset_id": ds["id"],
        "taxonomy_id": tax["id"],
        "method": "rule_based",
    })
    assert resp.status_code == 200
    assert len(resp.json()) == 4  # 4 turns


@pytest.mark.asyncio
async def test_classify_embedding(client):
    ds = await _upload_csv(client)
    tax = await _create_taxonomy(client)
    await _add_categories(client, tax["id"])
    resp = await client.post("/classify", json={
        "dataset_id": ds["id"],
        "taxonomy_id": tax["id"],
        "method": "embedding",
    })
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_classify_hybrid(client):
    ds = await _upload_csv(client)
    tax = await _create_taxonomy(client)
    await _add_categories(client, tax["id"])
    resp = await client.post("/classify", json={
        "dataset_id": ds["id"],
        "taxonomy_id": tax["id"],
        "method": "hybrid",
    })
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_classify_invalid_method(client):
    ds = await _upload_csv(client)
    tax = await _create_taxonomy(client)
    await _add_categories(client, tax["id"])
    resp = await client.post("/classify", json={
        "dataset_id": ds["id"],
        "taxonomy_id": tax["id"],
        "method": "nonexistent",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_classify_invalid_dataset(client):
    tax = await _create_taxonomy(client)
    await _add_categories(client, tax["id"])
    resp = await client.post("/classify", json={
        "dataset_id": 9999,
        "taxonomy_id": tax["id"],
        "method": "rule_based",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_classification_methods(client):
    resp = await client.get("/classify/methods")
    assert resp.status_code == 200
    methods = resp.json()
    method_ids = [m["id"] for m in methods]
    assert "rule_based" in method_ids
    assert "embedding" in method_ids
    assert "zero_shot" in method_ids
    assert "hybrid" in method_ids
    assert "transformer" in method_ids
    assert "llm_fewshot" in method_ids


@pytest.mark.asyncio
async def test_classification_results(client):
    ds = await _upload_csv(client)
    tax = await _create_taxonomy(client)
    await _add_categories(client, tax["id"])
    await client.post("/classify", json={
        "dataset_id": ds["id"],
        "taxonomy_id": tax["id"],
        "method": "rule_based",
    })
    resp = await client.get(f"/classify/results/{ds['id']}/{tax['id']}")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 2  # 2 conversations


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analytics_summary(client):
    ds = await _upload_csv(client)
    resp = await client.get(f"/analytics/summary/{ds['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_conversations"] == 2
    assert body["total_turns"] == 4


@pytest.mark.asyncio
async def test_analytics_distribution(client):
    ds = await _upload_csv(client)
    tax = await _create_taxonomy(client)
    await _add_categories(client, tax["id"])
    await client.post("/classify", json={
        "dataset_id": ds["id"],
        "taxonomy_id": tax["id"],
        "method": "rule_based",
    })
    resp = await client.get(f"/analytics/distribution/{ds['id']}/{tax['id']}")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_analytics_transitions(client):
    ds = await _upload_csv(client)
    tax = await _create_taxonomy(client)
    await _add_categories(client, tax["id"])
    await client.post("/classify", json={
        "dataset_id": ds["id"],
        "taxonomy_id": tax["id"],
        "method": "rule_based",
    })
    resp = await client.get(f"/analytics/transitions/{ds['id']}/{tax['id']}")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_experiment(client):
    ds = await _upload_csv(client)
    tax = await _create_taxonomy(client)
    await _add_categories(client, tax["id"])
    resp = await client.post("/experiments", json={
        "name": "Exp 1",
        "dataset_id": ds["id"],
        "taxonomy_id": tax["id"],
        "classification_method": "rule_based",
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "Exp 1"


@pytest.mark.asyncio
async def test_experiment_invalid_dataset(client):
    tax = await _create_taxonomy(client)
    resp = await client.post("/experiments", json={
        "name": "Bad Exp",
        "dataset_id": 9999,
        "taxonomy_id": tax["id"],
        "classification_method": "rule_based",
    })
    assert resp.status_code == 400
    assert "not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_experiment_invalid_taxonomy(client):
    ds = await _upload_csv(client)
    resp = await client.post("/experiments", json={
        "name": "Bad Exp",
        "dataset_id": ds["id"],
        "taxonomy_id": 9999,
        "classification_method": "rule_based",
    })
    assert resp.status_code == 400
    assert "not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_experiment_empty_name(client):
    ds = await _upload_csv(client)
    tax = await _create_taxonomy(client)
    resp = await client.post("/experiments", json={
        "name": "   ",
        "dataset_id": ds["id"],
        "taxonomy_id": tax["id"],
        "classification_method": "rule_based",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_run_experiment(client):
    ds = await _upload_csv(client)
    tax = await _create_taxonomy(client)
    await _add_categories(client, tax["id"])
    exp_resp = await client.post("/experiments", json={
        "name": "Run Test",
        "dataset_id": ds["id"],
        "taxonomy_id": tax["id"],
        "classification_method": "rule_based",
    })
    exp_id = exp_resp.json()["id"]
    resp = await client.post(f"/experiments/{exp_id}/run")
    assert resp.status_code == 200
    run = resp.json()
    run_id = run["id"]
    # Endpoint returns "pending" (background execution), poll for completion
    assert run["status"] in ("pending", "running", "completed")

    import asyncio
    for _ in range(50):
        await asyncio.sleep(0.1)
        poll = await client.get(f"/experiments/runs/{run_id}")
        run = poll.json()
        if run["status"] in ("completed", "failed"):
            break

    assert run["status"] == "completed"
    assert run["results_summary"] is not None


@pytest.mark.asyncio
async def test_list_runs(client):
    ds = await _upload_csv(client)
    tax = await _create_taxonomy(client)
    await _add_categories(client, tax["id"])
    exp_resp = await client.post("/experiments", json={
        "name": "Runs Test",
        "dataset_id": ds["id"],
        "taxonomy_id": tax["id"],
        "classification_method": "rule_based",
    })
    exp_id = exp_resp.json()["id"]
    run_resp = await client.post(f"/experiments/{exp_id}/run")
    run_id = run_resp.json()["id"]

    import asyncio
    for _ in range(50):
        await asyncio.sleep(0.1)
        poll = await client.get(f"/experiments/runs/{run_id}")
        if poll.json()["status"] in ("completed", "failed"):
            break

    resp = await client.get(f"/experiments/{exp_id}/runs")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_delete_experiment(client):
    ds = await _upload_csv(client)
    tax = await _create_taxonomy(client)
    exp_resp = await client.post("/experiments", json={
        "name": "Del Test",
        "dataset_id": ds["id"],
        "taxonomy_id": tax["id"],
        "classification_method": "rule_based",
    })
    exp_id = exp_resp.json()["id"]
    resp = await client.delete(f"/experiments/{exp_id}")
    assert resp.status_code == 200
    resp = await client.get(f"/experiments/{exp_id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Seed Demo
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_seed_demo(client):
    resp = await client.post("/seed-demo")
    assert resp.status_code == 200
    body = resp.json()
    assert body["conversations"] == 50
    assert body["total_turns"] > 0

    # Second call should say already exists
    resp2 = await client.post("/seed-demo")
    assert resp2.status_code == 200
    assert "already exists" in resp2.json()["detail"]
