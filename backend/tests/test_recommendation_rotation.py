from app.services.resume_copilot.rotation import next_page


def _pool(n):
    return [{"job_id": f"j{i}"} for i in range(n)]


def test_first_page_excludes_seen():
    page, recycled = next_page(_pool(5), exclude_ids={"j0", "j1"}, page_size=2)
    assert [p["job_id"] for p in page] == ["j2", "j3"]
    assert recycled is False


def test_recycle_when_all_seen():
    page, recycled = next_page(_pool(3), exclude_ids={"j0", "j1", "j2"}, page_size=2)
    assert [p["job_id"] for p in page] == ["j0", "j1"]
    assert recycled is True


def test_empty_pool():
    assert next_page([], exclude_ids=set(), page_size=5) == ([], False)
