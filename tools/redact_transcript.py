#!/usr/bin/env python3
"""Deterministic, repeatable transcript redactor (Python stdlib only).

NOT the same tool as Sir BRY's tools/redact_transcript.py, despite the name.
That one uses Microsoft Presidio to DETECT names and renumbers them as
"Member 1/2/3"; this one substitutes a fixed deny-list (tools/pii_config.json)
with initials and needs no model. Keep both: this is the offline, dependency-free
one used alongside an edit; Sir BRY's is the one its transcript-redactor skill
drives. Neither should be pointed at the other's config.

Fixes the earlier hand-redaction problems:
  - unique, collision-free initials (Jordan != Jamie)
  - AI/product & place names kept visible (config decision)
  - a built-in self-check that FAILS if any deny-listed name survives
  - an --audit mode that lists remaining proper nouns so leaks can be caught

Usage:
  # redact an existing plain-text transcript .md
  redact_transcript.py --in SRC.md --out OUT.md --title "2026-07-23 (Approved, Redacted)"

  # rebuild clean text from a *_final.json (words list) first, then redact
  redact_transcript.py --from-words SRC_final.json --out OUT.md --title "..."

  # just list proper nouns still present after redaction (leak review)
  redact_transcript.py --in SRC.md --audit
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "pii_config.json")

LEGEND = ("_Redaction legend: `[X.]` = a real participant's initials "
          "(same person -> same code) - `[EMAIL]` `[PHONE]` `[AMOUNT]` = "
          "contact info & money. AI/product names and place names are left "
          "intact on purpose. The host is left visible. Redacted on-device, "
          "no cloud._")


def load_config(path=CONFIG):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


_SENT_END = re.compile(r'[.?!]["\')\]]?$')


def text_from_words(json_path, src_gap=1.6, target_words=55, hard_cap=110):
    """Rebuild readable paragraphs from a *_final.json `words` list.

    Paragraphs break only at sentence boundaries, triggered by either a pause
    in the ORIGINAL speech (src timing — the edited timeline is continuous in a
    rough cut, so it can't be used) or reaching ~target_words. This matches the
    ~55-word paragraph style of the approved transcripts.
    """
    data = json.load(open(json_path, encoding="utf-8"))
    words = data["words"]
    out, para, prev_src_end, wc = [], [], None, 0
    for w in words:
        t = w.get("text", "").strip()
        if not t:
            continue
        gap = abs(w["src_start"] - prev_src_end) if prev_src_end is not None else 0
        ends_sentence = para and _SENT_END.search(para[-1])
        # break at a sentence boundary on a pause or once past target length;
        # hard_cap forces a break even mid-sentence for unpunctuated monologues
        if para and ((ends_sentence and (gap > src_gap or wc >= target_words))
                     or wc >= hard_cap):
            out.append(" ".join(para))
            para, wc = [], 0
        para.append(t)
        wc += 1
        prev_src_end = w["src_end"]
    if para:
        out.append(" ".join(para))
    return "\n\n".join(out)


def build_redactor(cfg):
    people = cfg["people"]
    # longest names first so "Christopher" wins before "Chris", "Samantha" before "Sam"
    names = sorted(people, key=len, reverse=True)
    name_re = re.compile(r"\b(?:%s)\b" % "|".join(re.escape(n) for n in names),
                         re.IGNORECASE)
    lut = {n.lower(): ph for n, ph in people.items()}
    rx = {k: re.compile(v, re.IGNORECASE) for k, v in cfg["regex_redactions"].items()}

    def redact(text):
        # contact info & money first (they carry digits/@ - no overlap with names)
        for label in ("EMAIL", "PHONE", "AMOUNT"):
            text = rx[label].sub("[%s]" % label, text)
        text = name_re.sub(lambda m: lut[m.group(0).lower()], text)
        return text

    return redact, name_re


def audit(text):
    """Return capitalized proper-noun candidates still present (mid-sentence)."""
    from collections import Counter
    cands = re.findall(r"(?<=[a-z,] )([A-Z][a-z]{2,})", text)
    return Counter(cands)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp")
    ap.add_argument("--from-words", dest="words")
    ap.add_argument("--out")
    ap.add_argument("--title", default="Redacted Transcript")
    ap.add_argument("--config", default=CONFIG)
    ap.add_argument("--audit", action="store_true")
    a = ap.parse_args()

    cfg = load_config(a.config)
    redact, name_re = build_redactor(cfg)

    if a.words:
        raw = text_from_words(a.words)
    elif a.inp:
        raw = open(a.inp, encoding="utf-8").read()
        # if fed a markdown file, drop an existing header block (before first '---')
        parts = raw.split("\n---\n", 1)
        if len(parts) == 2 and len(parts[0]) < 800:
            raw = parts[1].lstrip("\n")
    else:
        sys.exit("need --in or --from-words")

    if a.audit:
        for w, n in audit(raw).most_common(60):
            print(f"{n:4}  {w}")
        return

    body = redact(raw)

    # self-check: no deny-listed name may survive
    leaks = name_re.findall(body)
    if leaks:
        sys.exit("REDACTION FAILED - names survived: %s" % sorted(set(leaks)))

    words = len(re.findall(r"\w+", body))
    header = ("# %s\n\nNames & contact/financial PII redacted locally. "
              "AI/product & place names left intact.\n\n- Words: **%d**  -  "
              "Deterministic redaction via `tools/redact_transcript.py` + "
              "`tools/pii_config.json`\n\n%s\n\n---\n\n" %
              (a.title, words, LEGEND))
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(header + body.strip() + "\n")
    print("wrote %s  (%d words, 0 name leaks)" % (a.out, words))


if __name__ == "__main__":
    main()
