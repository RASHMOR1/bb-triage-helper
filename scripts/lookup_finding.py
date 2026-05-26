#!/usr/bin/env python3
"""Print a focused bug-bounty triage packet for one finding ID."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path


SOURCE_EXTS = {
    ".sol",
    ".vy",
    ".rs",
    ".go",
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".java",
    ".kt",
    ".cs",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".move",
}
HELPER_NAME = "bb-triage-helper"
IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".cache",
    ".next",
    ".nuxt",
    ".turbo",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "out",
    "cache",
    "artifacts",
    "broadcast",
    "coverage",
    "typechain",
    "typechain-types",
}
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "but",
    "by",
    "can",
    "cannot",
    "could",
    "does",
    "for",
    "from",
    "has",
    "have",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "may",
    "must",
    "not",
    "of",
    "on",
    "or",
    "should",
    "that",
    "the",
    "their",
    "then",
    "there",
    "this",
    "to",
    "via",
    "when",
    "where",
    "which",
    "will",
    "with",
    "would",
}


def canonical_id(value: str) -> str:
    match = re.match(r"^([A-Za-z]+)-?0*(\d+)$", value.strip())
    if not match:
        return value.strip().upper()
    return f"{match.group(1).upper()}-{int(match.group(2))}"


def safe_read_text(path: Path, max_bytes: int = 1_000_000) -> str:
    data = path.read_bytes()[:max_bytes]
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def fetch_url(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": f"{HELPER_NAME}/1.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("content-type", "")
        encoding = "utf-8"
        if "charset=" in content_type:
            encoding = content_type.split("charset=", 1)[1].split(";", 1)[0].strip()
        return response.read(1_000_000).decode(encoding, errors="replace")


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str) -> set[str]:
    tokens = set()
    for raw in re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", text):
        token = raw.lower()
        if token not in STOPWORDS and not token.isdigit():
            tokens.add(token)
    return tokens


def clean_comment(raw: str) -> str:
    text = re.sub(r"^\s*/\*\*?", "", raw)
    text = re.sub(r"\*/\s*$", "", text)
    lines = []
    for line in text.splitlines():
        line = re.sub(r"^\s*(///|//|#|--|/\*+|\*)\s?", "", line)
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def extract_comments(text: str, suffix: str) -> str:
    if suffix in {".sol", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".cs", ".c", ".cc", ".cpp", ".h", ".hpp", ".rs", ".go"}:
        patterns = [
            r"/\*\*[\s\S]*?\*/",
            r"(?m)^\s*///.*(?:\n\s*///.*)*",
            r"(?m)^\s*//\s*(?:@notice|@dev|TODO|Invariant|Assumption|Spec|NOTE).*$",
        ]
    elif suffix == ".py":
        patterns = [
            r'"""[\s\S]*?"""',
            r"'''[\s\S]*?'''",
            r"(?m)^\s*#\s*(?:TODO|Invariant|Assumption|Spec|NOTE).*$",
        ]
    else:
        patterns = [r"(?m)^\s*(?:#|--)\s*(?:TODO|Invariant|Assumption|Spec|NOTE).*$"]

    blocks = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            comment = clean_comment(match.group(0).strip("\"'"))
            if len(comment) >= 20:
                blocks.append(comment)
    return "\n\n".join(blocks)


def read_doc_text(doc: dict) -> str:
    if doc.get("fetched_text"):
        return doc["fetched_text"]
    path_value = doc["path"]
    if path_value.startswith(("http://", "https://")):
        try:
            return fetch_url(path_value)
        except Exception:
            return doc.get("excerpt", "")

    path = Path(path_value)
    if not path.is_file():
        return doc.get("excerpt", "")
    text = safe_read_text(path)
    if doc.get("kind") == "source-comments":
        return extract_comments(text, path.suffix.lower())
    return text


def excerpt_around(text: str, terms: list[str], max_chars: int = 420) -> str:
    compact = normalize_ws(text)
    if not compact:
        return ""
    lower = compact.lower()
    positions = [lower.find(term.lower()) for term in terms if term and lower.find(term.lower()) >= 0]
    if not positions:
        return compact[:max_chars].rstrip() + ("..." if len(compact) > max_chars else "")
    center = min(positions)
    start = max(0, center - max_chars // 3)
    end = min(len(compact), start + max_chars)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(compact) else ""
    return prefix + compact[start:end].strip() + suffix


def should_skip(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path
    return bool(set(rel.parts) & IGNORED_DIRS)


def iter_source_files(root: Path):
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in SOURCE_EXTS and not should_skip(path, root):
            yield path


def select_terms(finding: dict, max_terms: int = 16) -> list[str]:
    identifiers = [item for item in finding.get("identifiers", []) if len(item) >= 3]
    tokens = [item for item in finding.get("tokens", []) if len(item) >= 4]
    ordered = []
    for item in identifiers + tokens:
        low = item.lower()
        if low not in {value.lower() for value in ordered}:
            ordered.append(item)
    return ordered[:max_terms]


def doc_hits(context: dict, finding: dict, max_hits: int = 8) -> list[dict]:
    finding_terms = set(finding.get("tokens", []))
    finding_identifiers = {item.lower() for item in finding.get("identifiers", [])}
    hits = []
    for doc in context.get("docs", []):
        text = read_doc_text(doc)
        doc_terms = tokenize(text)
        doc_identifiers = {item.lower() for item in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b", text)}
        matched_terms = sorted(finding_terms & doc_terms)[:16]
        matched_identifiers = sorted(finding_identifiers & doc_identifiers)[:16]
        if not matched_terms and not matched_identifiers:
            continue
        score = len(matched_terms) + (3 * len(matched_identifiers))
        terms_for_excerpt = matched_identifiers[:4] + matched_terms[:4]
        hits.append(
            {
                "display_path": doc.get("display_path", doc["path"]),
                "source": doc.get("source", "unknown"),
                "kind": doc.get("kind", "document"),
                "score": score,
                "matched_terms": matched_terms,
                "matched_identifiers": matched_identifiers,
                "excerpt": excerpt_around(text, terms_for_excerpt),
            }
        )
    return sorted(hits, key=lambda item: item["score"], reverse=True)[:max_hits]


def code_hits(context: dict, finding: dict, max_hits: int = 14) -> list[dict]:
    repo_root = Path(context["repo_root"])
    terms = select_terms(finding)
    if not terms:
        return []
    hits = []
    for path in iter_source_files(repo_root):
        try:
            text = safe_read_text(path)
        except Exception:
            continue
        lower = text.lower()
        matched = [term for term in terms if term.lower() in lower]
        if not matched:
            continue
        score = sum(3 if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", term) else 1 for term in matched)
        lines = []
        for number, line in enumerate(text.splitlines(), 1):
            if any(term.lower() in line.lower() for term in matched):
                lines.append({"line": number, "text": line.strip()[:180]})
            if len(lines) >= 4:
                break
        try:
            display_path = str(path.relative_to(repo_root))
        except ValueError:
            display_path = str(path)
        hits.append(
            {
                "display_path": display_path,
                "score": score,
                "matched": matched[:10],
                "lines": lines,
            }
        )
    return sorted(hits, key=lambda item: item["score"], reverse=True)[:max_hits]


def find_related(context: dict, finding: dict) -> list[str]:
    unique_id = finding["unique_id"]
    related = set()
    for group in context.get("groups", {}).get("duplicate_groups", []):
        if unique_id in group:
            related.update(group)
    for group in context.get("groups", {}).get("related_groups", []):
        ids = group.get("ids", [])
        if unique_id in ids:
            related.update(ids)
    related.discard(unique_id)
    return sorted(related)


def print_deployment_context(context: dict) -> None:
    deployment = context.get("deployment", {})
    deployment_path = Path(context.get("output_dir", ".")) / "deployment-context.md"

    print("## Deployment / On-chain Context")
    print()
    print(f"- Deployment artifact: `{deployment_path}`")
    if context.get("protocol_name"):
        print(f"- Protocol name: `{context['protocol_name']}`")

    chains = deployment.get("chains", [])
    if chains:
        print("- Candidate chains from setup:")
        for item in chains[:8]:
            print(f"  - {item['chain']} ({item.get('evidence_count', 0)} evidence hits)")
    else:
        print("- No candidate chain was discovered during setup.")

    addresses = deployment.get("addresses", [])
    if addresses:
        print("- Candidate contract/program addresses from setup:")
        for item in addresses[:12]:
            nearby = ", ".join(item.get("nearby_chains", [])) or "unknown chain context"
            labels = ", ".join(item.get("labels", [])[:2])
            label_suffix = f" - {labels}" if labels else ""
            print(f"  - `{item['address']}` ({item['type']}, {nearby}){label_suffix}")
    else:
        print("- No candidate contract or program address was discovered during setup.")

    notes = deployment.get("notes", [])
    for note in notes[:4]:
        print(f"- Note: {note}")
    print()


def resolve_finding(context: dict, finding_id: str) -> dict:
    wanted = canonical_id(finding_id)
    for finding in context.get("findings", []):
        if canonical_id(finding.get("id", "")) == wanted or finding.get("canonical_id") == wanted or finding.get("unique_id") == wanted:
            return finding
    available = ", ".join(finding.get("id", finding.get("unique_id", "")) for finding in context.get("findings", [])[:30])
    raise SystemExit(f"Finding not found: {finding_id}. Available examples: {available}")


def truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 40].rstrip() + "\n\n[truncated by lookup_finding.py]\n"


def print_markdown(context: dict, finding: dict, max_content_chars: int) -> None:
    print(f"# Triage Packet: {finding['id']} {finding['title']}")
    print()

    related = find_related(context, finding)
    print("## Duplicate Status")
    print()
    if related:
        by_unique = {item["unique_id"]: item for item in context.get("findings", [])}
        print("- Candidate duplicate or related finding detected during setup:")
        for item in related:
            other = by_unique.get(item)
            if other:
                print(f"  - `{other['id']}` {other['title']}")
    else:
        print("- No duplicate or related finding was detected during setup.")
    print()

    print("## Source")
    print()
    print(f"- Findings file: `{context['findings_file']}:{finding['start_line']}`")
    print(f"- Repo root: `{context['repo_root']}`")
    print(f"- Setup output: `{context['output_dir']}`")
    print()

    print("## Finding Text")
    print()
    print(truncate(finding["content"], max_content_chars))
    print()

    print("## Documentation Hits")
    print()
    hits = doc_hits(context, finding)
    if not hits:
        print("- No matching docs, NatSpec, or comment blocks were found.")
    for hit in hits:
        labels = []
        if hit["matched_identifiers"]:
            labels.append("identifiers: " + ", ".join(f"`{value}`" for value in hit["matched_identifiers"][:6]))
        if hit["matched_terms"]:
            labels.append("terms: " + ", ".join(f"`{value}`" for value in hit["matched_terms"][:6]))
        suffix = f" ({'; '.join(labels)})" if labels else ""
        print(f"- `{hit['display_path']}` ({hit['source']}, {hit['kind']}){suffix}")
        if hit["excerpt"]:
            print(f"  - {hit['excerpt']}")
    print()

    print_deployment_context(context)

    print("## Candidate Code References")
    print()
    refs = code_hits(context, finding)
    if not refs:
        print("- No candidate code references found from finding terms.")
    for ref in refs:
        matched = ", ".join(f"`{term}`" for term in ref["matched"][:8])
        print(f"- `{ref['display_path']}` matches {matched}")
        for line in ref["lines"]:
            print(f"  - L{line['line']}: `{line['text']}`")
    print()

    print("## Triage Reminder")
    print()
    print("- Start the final response with duplicate status: Duplicate, Near-duplicate, Related, or No duplicate detected.")
    print("- Explain the claim in simple, educational terms for someone new to this protocol.")
    print("- Check docs/spec/NatSpec/comments plus previous audit reports, audit contest findings, and known-issue docs for the same or similar issue.")
    print("- Add a separate Current On-chain State Assessment section before the numerical example.")
    print("- In that section, verify current deployed state, value at risk, repeatability, configuration/admin assumptions, historical preconditions, intentional behavior, and whether the bug is already known from previous audits, audit contests, program pages, docs, GitHub, or public discussions.")
    print("- If current state does not support a real exploitable issue, recommend skipping submission or marking the finding invalid/needs more information.")
    print("- Build a numerical example with context first: what should happen, what the code does, and why the numbers matter.")
    print("- Trace the implementation and try both to validate and invalidate the report.")
    print("- Combine protocol analysis and verdict in one final section, including caveats when relevant.")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Look up one bug-bounty finding from triage-context.json.")
    parser.add_argument("finding_id", help="Finding ID, for example M-24.")
    parser.add_argument(
        "--context",
        default="bb-triage-helper-output/triage-context.json",
        help="Path to triage-context.json.",
    )
    parser.add_argument("--max-content-chars", type=int, default=14_000)
    parser.add_argument("--json", action="store_true", help="Print structured JSON instead of markdown.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    context_path = Path(args.context).expanduser().resolve()
    if not context_path.is_file():
        raise SystemExit(f"Context file not found: {context_path}")
    context = json.loads(context_path.read_text(encoding="utf-8"))
    finding = resolve_finding(context, args.finding_id)

    if args.json:
        payload = {
            "finding": finding,
            "related": find_related(context, finding),
            "doc_hits": doc_hits(context, finding),
            "code_hits": code_hits(context, finding),
            "deployment": context.get("deployment", {}),
        }
        print(json.dumps(payload, indent=2))
    else:
        print_markdown(context, finding, args.max_content_chars)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
