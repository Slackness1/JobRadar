"""Pytest 配置 — 注册 `eval` mark,普通 `pytest tests/` 默认跳过 eval 套件。"""


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "eval: 离线评测套件 — 调真 LLM,慢、花钱。显式 `-m eval` 才跑。",
    )


def pytest_collection_modifyitems(config, items):
    """如果跑命令没带 `-m eval`,自动跳过 eval marker 的用例。"""
    if config.getoption("-m") and "eval" in (config.getoption("-m") or ""):
        return  # 用户显式要跑 eval
    skip_eval = __import__("pytest").mark.skip(reason="eval suite — 跑 `pytest tests/eval/ -m eval` 才执行")
    for item in items:
        if "eval" in item.keywords:
            item.add_marker(skip_eval)
