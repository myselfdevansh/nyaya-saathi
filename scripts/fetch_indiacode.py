"""
Download Central Acts, section by section, from India Code (indiacode.gov.in),
the official Government of India repository of legislation.

India Code runs DSpace, which exposes a public REST API. Each section of a
Central Act is stored as its own record, with the official section text in the
`dc.identifier.section_page_note` field. This script:

  1. finds the official Act ID for each Act name in ACTS,
  2. pages through every SECTION record of that Act,
  3. cleans the HTML into plain text,
  4. writes:
       data/raw_acts/<slug>.json      raw API metadata (for audit)
       data/processed/sections.jsonl  one cleaned section per line (for RAG)
       data/processed/manifest.csv    what was downloaded, with counts

Usage:
    python scripts/fetch_indiacode.py                # all Acts in ACTS
    python scripts/fetch_indiacode.py "Limitation Act, 1963"   # just one

To add coverage, add an Act's exact title to ACTS and rerun.
"""

import csv
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://indiacode.gov.in/server/api/discover/search/objects"
SITE = "https://indiacode.gov.in"
ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw_acts"
OUT_DIR = ROOT / "data" / "processed"

# Everyday-problem Central Acts. Titles must match India Code's title.
ACTS = [
    # Consumer & contracts
    "The Consumer Protection Act, 2019",
    "The Indian Contract Act, 1872",
    "The Specific Relief Act, 1963",
    "The Limitation Act, 1963",
    "The Sale of Goods Act, 1930",
    # Money & cheques
    "The Negotiable Instruments Act, 1881",
    # Employment
    "The Code on Wages, 2019",
    # Not available as Central section records on India Code (Nov 2026); their
    # subject matter now sits in the Code on Wages / Code on Social Security.
    # Verify their status before relying on them.
    # "The Payment of Wages Act, 1936",
    # "The Payment of Gratuity Act, 1972",
    "The Industrial Relations Code, 2020",
    "The Code on Social Security, 2020",
    "The Sexual Harassment of Women at Workplace (Prevention, Prohibition and Redressal) Act, 2013",
    # Housing & property
    "The Transfer of Property Act, 1882",
    "The Real Estate (Regulation and Development) Act, 2016",
    # Criminal (new codes from 1 July 2024)
    "The Bharatiya Nyaya Sanhita, 2023",
    "The Bharatiya Nagarik Suraksha Sanhita, 2023",
    "The Bharatiya Sakshya Adhiniyam, 2023",
    # Family & vulnerable groups
    "The Protection of Women from Domestic Violence Act, 2005",
    "The Maintenance and Welfare of Parents and Senior Citizens Act, 2007",
    "The Dowry Prohibition Act, 1961",
    # Digital & government
    "The Information Technology Act, 2000",
    "The Digital Personal Data Protection Act, 2023",
    "The Right to Information Act, 2005",
    # Access to justice
    "The Legal Services Authorities Act, 1987",
    # Accidents
    "The Motor Vehicles Act, 1988",
    # Family law agent
    "The Hindu Marriage Act, 1955",
    "The Special Marriage Act, 1954",
    "The Divorce Act, 1869",
    "The Dissolution of Muslim Marriages Act, 1939",
    "The Muslim Women (Protection of Rights on Marriage) Act, 2019",
    "The Hindu Adoptions and Maintenance Act, 1956",
    "The Hindu Minority and Guardianship Act, 1956",
    "The Guardians and Wards Act, 1890",
    "The Family Courts Act, 1984",
    "The Hindu Succession Act, 1956",
    "The Indian Succession Act, 1925",
    "The Prohibition of Child Marriage Act, 2006",
    # Banking & financial consumer agent
    "The Banking Regulation Act, 1949",
    "The Reserve Bank of India Act, 1934",
    "The Payment and Settlement Systems Act, 2007",
    "The Securitisation and Reconstruction of Financial Assets and Enforcement of Security Interest Act, 2002",
    "The Recovery of Debts and Bankruptcy Act, 1993",
    "The Credit Information Companies (Regulation) Act, 2005",
    "The Banning of Unregulated Deposit Schemes Act, 2019",
    # Consumer agent: insurance
    "The Insurance Act, 1938",
    # Property agent
    "The Registration Act, 1908",
    "The Indian Stamp Act, 1899",
    "The Indian Easements Act, 1882",
    "The Partition Act, 1893",
    "The Code of Civil Procedure, 1908",
    # Employment agent
    "The Occupational Safety, Health and Working Conditions Code, 2020",
]

PAGE_SIZE = 100
PAUSE = 0.4  # seconds between requests: be polite to a government server


def get_json(params, retries=3):
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "ai-lawyer-research/0.1"}
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception as e:  # network hiccups on gov servers are common
            if attempt == retries - 1:
                raise
            print(f"    retry {attempt + 1} after error: {e}")
            time.sleep(3 * (attempt + 1))


def meta(item, key, default=""):
    vals = item.get("metadata", {}).get(key)
    return vals[0]["value"] if vals else default


def norm(title):
    t = title.lower().strip()
    t = re.sub(r"^the\s+", "", t)
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def objects(resp):
    sr = resp["_embedded"]["searchResult"]
    return [o["_embedded"]["indexableObject"] for o in sr["_embedded"]["objects"]], sr["page"]


def find_act_id(title):
    """Return the CENTRAL act_id for an Act title, or None."""
    want = norm(title)
    resp = get_json({"query": f'"{title}"', "dsoType": "ITEM", "size": 100})
    items, _ = objects(resp)
    for it in items:
        if meta(it, "dc.identifier.state_name") != "CENTRAL":
            continue
        name = meta(it, "dc.identifier.act_name") or it.get("name", "")
        if norm(name) == want:
            return meta(it, "dc.identifier.act_id")
    return None


def clean_html(raw):
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", raw)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def section_sort_key(num):
    m = re.match(r"(\d+)([A-Za-z]*)", num or "")
    return (int(m.group(1)), m.group(2)) if m else (10**9, num or "")


def fetch_sections(act_id):
    sections, page = [], 0
    while True:
        resp = get_json({
            "query": f'dc.identifier.act_id:"{act_id}"',
            "dsoType": "ITEM",
            "size": PAGE_SIZE,
            "page": page,
        })
        items, info = objects(resp)
        sections += [it for it in items if meta(it, "dc.identifier.collection") == "SECTION"]
        page += 1
        if page >= info.get("totalPages", 0):
            break
        time.sleep(PAUSE)
    return sections


def slugify(title):
    return re.sub(r"[^a-z0-9]+", "_", norm(title)).strip("_")[:80]


def main(titles):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = OUT_DIR / "sections.jsonl"
    manifest_path = OUT_DIR / "manifest.csv"

    # When fetching a subset, keep previously fetched Acts.
    existing = {}
    if jsonl_path.exists() and titles != ACTS:
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            existing.setdefault(rec["act"], []).append(rec)

    manifest, all_records = [], dict(existing)
    for title in titles:
        print(f"- {title}")
        try:
            act_id = find_act_id(title)
            time.sleep(PAUSE)
            if not act_id:
                print("    NOT FOUND as a Central Act; check the exact title on indiacode.gov.in")
                manifest.append({"act": title, "status": "not_found", "sections": 0, "empty_text": 0, "act_id": ""})
                continue
            raw = fetch_sections(act_id)
        except Exception as e:
            print(f"    FAILED: {e}")
            manifest.append({"act": title, "status": f"error: {e}", "sections": 0, "empty_text": 0, "act_id": ""})
            continue

        (RAW_DIR / f"{slugify(title)}.json").write_text(
            json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        records = []
        for it in raw:
            num = meta(it, "dc.identifier.section_number")
            records.append({
                "id": f"{slugify(title)}__s{num}",
                "act": title,
                "act_year": meta(it, "dc.date.act_year"),
                "act_id": act_id,
                "section": num,
                "heading": it.get("name", "").strip(),
                "text": clean_html(meta(it, "dc.identifier.section_page_note")),
                "repealed": meta(it, "dc.identifier.repealed", "false"),
                "source_url": f"{SITE}/handle/{it.get('handle', '')}" if it.get("handle") else SITE,
            })
        # Same section can appear twice; keep the longer text.
        dedup = {}
        for r in records:
            if r["section"] not in dedup or len(r["text"]) > len(dedup[r["section"]]["text"]):
                dedup[r["section"]] = r
        records = sorted(dedup.values(), key=lambda r: section_sort_key(r["section"]))
        all_records[title] = records
        empty = sum(1 for r in records if not r["text"])
        print(f"    {len(records)} sections ({empty} with empty text)")
        manifest.append({"act": title, "status": "ok", "sections": len(records), "empty_text": empty, "act_id": act_id})

    with jsonl_path.open("w", encoding="utf-8") as f:
        for recs in all_records.values():
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    # When fetching a subset, keep the manifest rows of the other Acts.
    if manifest_path.exists() and titles != ACTS:
        fetched = {m["act"] for m in manifest}
        with manifest_path.open(newline="", encoding="utf-8") as f:
            manifest = [r for r in csv.DictReader(f) if r["act"] not in fetched] + manifest
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["act", "status", "sections", "empty_text", "act_id"])
        w.writeheader()
        w.writerows(manifest)
    total = sum(len(v) for v in all_records.values())
    print(f"\nWrote {total} sections to {jsonl_path}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main(sys.argv[1:] or ACTS)
