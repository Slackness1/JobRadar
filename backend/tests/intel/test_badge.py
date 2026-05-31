from app.services.intel.badge import synth_badge

def test_verified_is_three_stars():
    assert synth_badge(source_score=0.3, content_tier="low", cross="verified") == 3

def test_single_high_or_strong_is_two():
    assert synth_badge(source_score=0.7, content_tier="med", cross="single") == 2
    assert synth_badge(source_score=0.3, content_tier="high", cross="single") == 2

def test_single_weak_is_one():
    assert synth_badge(source_score=0.3, content_tier="low", cross="single") == 1

def test_n_three_rescues_to_two():
    assert synth_badge(source_score=0.3, content_tier="med", cross="single", n=3) == 2
