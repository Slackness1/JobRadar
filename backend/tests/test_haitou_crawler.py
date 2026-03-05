from app.services.haitou_crawler import extract_next_data_json, parse_time_range, split_job_text


def test_extract_next_data_json_from_script_tag():
    html = '<html><body><script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"listJob":[{"id":1}]}}}</script></body></html>'
    data = extract_next_data_json(html)
    assert data["props"]["pageProps"]["listJob"][0]["id"] == 1


def test_parse_time_range():
    start, end = parse_time_range("2026.03.05-2026.06.05")
    assert start is not None
    assert end is not None
    assert start.strftime("%Y-%m-%d") == "2026-03-05"
    assert end.strftime("%Y-%m-%d") == "2026-06-05"


def test_split_job_text_by_sections():
    duty, req = split_job_text("岗位职责：负责A\n岗位要求：熟悉B")
    assert "负责A" in duty
    assert "熟悉B" in req
