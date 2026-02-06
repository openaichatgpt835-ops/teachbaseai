"""Contract: install template uses BX24.installFinish and not BX24Js.installFinish."""
from pathlib import Path


def test_install_template_uses_bx24_install_finish():
    tpl = Path("apps/backend/templates/install.html").read_text(encoding="utf-8")
    assert "BX24Js.installFinish" not in tpl
    assert "B24Js.installFinish" not in tpl
    assert "BX24.installFinish" in tpl
    assert "BX24.init" in tpl
