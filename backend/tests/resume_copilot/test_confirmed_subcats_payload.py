from app.schemas_resume_copilot import ResumePreferencePayload


def test_confirmed_sub_cats_defaults_empty():
    p = ResumePreferencePayload()
    assert p.confirmed_sub_cats == []


def test_confirmed_sub_cats_roundtrips_through_model_dump():
    p = ResumePreferencePayload(
        preferred_tracks=["公募/资管·投研"],
        confirmed_sub_cats=["公募权益研究员", "行业研究员·消费"],
    )
    dumped = p.model_dump()
    assert dumped["confirmed_sub_cats"] == ["公募权益研究员", "行业研究员·消费"]
    legacy = {"preferred_tracks": ["公募/资管·投研"]}
    assert ResumePreferencePayload(**legacy).confirmed_sub_cats == []
