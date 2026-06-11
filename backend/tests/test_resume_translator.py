from app.services.resume_copilot import translator as T


def test_format_date_en_single():
    assert T.format_date_en("2024-06") == "Jun 2024"


def test_format_date_en_range():
    assert T.format_date_en("2024-06 - 2024-12") == "Jun 2024 – Dec 2024"


def test_format_date_en_passthrough_unknown():
    assert T.format_date_en("2024 寒假") == "2024 寒假"


def test_numbers_in_extracts():
    assert "0.8" in T.numbers_in("single-factor Sharpe > 0.8")
    assert "12" in T.numbers_in("submitted 12 factors")


def test_en_section_label_by_id():
    assert T.en_section_label("intern", "实习经历") == "Work Experience"
    assert T.en_section_label("proj", "项目经历") == "Projects"


def test_en_section_label_unknown_falls_back_to_source():
    assert T.en_section_label("custom", "证书") == "证书"
