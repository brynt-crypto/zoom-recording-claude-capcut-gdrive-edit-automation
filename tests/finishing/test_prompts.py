from pathlib import Path
from finishing.beats import TREATMENTS

PROMPTS = Path("finishing/prompts")

def test_all_prompt_files_present_and_nonempty():
    names = ["00_system", "01_beat_selection", "02_report", "03_manifest",
             "04_subtitles", "05_overlays", "06_punch_ins", "07_end_screen"]
    for n in names:
        f = PROMPTS / f"{n}.md"
        assert f.exists() and f.read_text(encoding="utf-8").strip()

def test_manifest_prompt_documents_every_treatment():
    txt = (PROMPTS / "03_manifest.md").read_text(encoding="utf-8")
    for t in TREATMENTS:
        assert t in txt, f"manifest prompt missing treatment '{t}'"
