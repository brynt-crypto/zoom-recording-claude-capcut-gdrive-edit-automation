# tests/finishing/test_skill_doc.py
from pathlib import Path

DOC = Path(".claude/commands/capcut-finishing-editor.md")

def test_skill_doc_covers_the_flow():
    assert DOC.exists()
    txt = DOC.read_text(encoding="utf-8").lower()
    for needle in ["--prep", "finishing_manifest.json", "review", "capcut",
                   "(cfe edit)", "-m finishing.pipeline"]:
        assert needle in txt, f"skill doc missing '{needle}'"
