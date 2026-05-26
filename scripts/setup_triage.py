#!/usr/bin/env python3
"""Build setup artifacts for bug-bounty finding triage."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import sys
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


VERSION = "1.1"
HELPER_NAME = "bb-triage-helper"

FINDING_ID_RE = re.compile(
    r"(?<![A-Za-z0-9])((?:H|M|L|I|G|NC|QA|R|C|S|A)-?\d{1,4})(?![A-Za-z0-9])",
    re.IGNORECASE,
)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

DOC_EXTS = {".md", ".mdx", ".rst", ".txt", ".adoc"}
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
DEPLOYMENT_EXTS = DOC_EXTS | SOURCE_EXTS | {
    ".cfg",
    ".conf",
    ".csv",
    ".env",
    ".ini",
    ".json",
    ".jsonc",
    ".toml",
    ".yaml",
    ".yml",
}
DEPLOYMENT_NAME_RE = re.compile(
    r"(address|addresses|blockscout|chain|chains|contract|contracts|deploy|deployment|"
    r"etherscan|explorer|foundry|hardhat|mainnet|network|program|proxy|scope|viem|wagmi)",
    re.IGNORECASE,
)
EVM_ADDRESS_RE = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
SOLANA_PROGRAM_RE = re.compile(
    r"\b(?:program(?:\s+id)?|programId|program_id|address)\s*[:=]\s*[`'\"]?"
    r"([1-9A-HJ-NP-Za-km-z]{32,44})",
    re.IGNORECASE,
)
URL_RE = re.compile(r"https?://[^\s<>)\]\"']+")
IGNORED_EVM_ADDRESSES = {
    "0x0000000000000000000000000000000000000000",
    "0x000000000000000000000000000000000000dead",
    "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
}
CHAIN_PATTERNS: list[tuple[str, list[str]]] = [
    ("Ethereum mainnet", [r"\bethereum\s+mainnet\b", r"\bethereum\b", r"\bchain\s*id\s*[:=]?\s*1\b", r"\betherscan\.io\b"]),
    ("Arbitrum One", [r"\barbitrum(?:\s+one)?\b", r"\bchain\s*id\s*[:=]?\s*42161\b", r"\barbiscan\.io\b"]),
    ("Optimism", [r"\boptimism\b", r"\bop\s+mainnet\b", r"\bchain\s*id\s*[:=]?\s*10\b", r"\boptimistic\.etherscan\.io\b"]),
    ("Base", [r"\bbase\s+(?:mainnet|chain|network)\b", r"\bchain\s*id\s*[:=]?\s*8453\b", r"\bbasescan\.org\b"]),
    ("Polygon", [r"\bpolygon\b", r"\bmatic\b", r"\bchain\s*id\s*[:=]?\s*137\b", r"\bpolygonscan\.com\b"]),
    ("Avalanche C-Chain", [r"\bavalanche\b", r"\bc-chain\b", r"\bchain\s*id\s*[:=]?\s*43114\b", r"\bsnowtrace\.io\b"]),
    ("BNB Chain", [r"\bbnb\s+chain\b", r"\bbsc\b", r"\bchain\s*id\s*[:=]?\s*56\b", r"\bbscscan\.com\b"]),
    ("Gnosis Chain", [r"\bgnosis\s+chain\b", r"\bxdai\b", r"\bchain\s*id\s*[:=]?\s*100\b", r"\bgnosisscan\.io\b"]),
    ("Fantom", [r"\bfantom\b", r"\bchain\s*id\s*[:=]?\s*250\b", r"\bftmscan\.com\b"]),
    ("Celo", [r"\bcelo\b", r"\bchain\s*id\s*[:=]?\s*42220\b", r"\bceloscan\.io\b"]),
    ("zkSync Era", [r"\bzksync(?:\s+era)?\b", r"\bchain\s*id\s*[:=]?\s*324\b", r"\bexplorer\.zksync\.io\b"]),
    ("Scroll", [r"\bscroll\b", r"\bchain\s*id\s*[:=]?\s*534352\b", r"\bscrollscan\.com\b"]),
    ("Linea", [r"\blinea\b", r"\bchain\s*id\s*[:=]?\s*59144\b", r"\blineascan\.build\b"]),
    ("Mantle", [r"\bmantle\b", r"\bchain\s*id\s*[:=]?\s*5000\b", r"\bmantlescan\.xyz\b"]),
    ("Blast", [r"\bblast\b", r"\bchain\s*id\s*[:=]?\s*81457\b", r"\bblastscan\.io\b"]),
    ("Mode", [r"\bmode\s+(?:mainnet|network|chain)\b", r"\bchain\s*id\s*[:=]?\s*34443\b", r"\bmodescan\.io\b"]),
    ("Solana", [r"\bsolana\b", r"\bexplorer\.solana\.com\b", r"\bsolscan\.io\b"]),
    ("Sui", [r"\bsui\b", r"\bsuiscan\.xyz\b"]),
    ("Aptos", [r"\baptos\b", r"\baptoscan\.com\b"]),
]
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


def display_id(value: str) -> str:
    match = re.match(r"^([A-Za-z]+)-?(\d+)$", value.strip())
    if not match:
        return value.strip().upper()
    return f"{match.group(1).upper()}-{match.group(2)}"


def safe_read_text(path: Path, max_bytes: int = 1_000_000) -> str:
    data = path.read_bytes()[:max_bytes]
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def fetch_url(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": f"{HELPER_NAME}/{VERSION}"},
    )
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


def extract_identifiers(text: str) -> set[str]:
    identifiers = set(re.findall(r"`([A-Za-z_][A-Za-z0-9_]*)`", text))
    identifiers.update(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*\(\))", text))
    identifiers.update(re.findall(r"\b([A-Z][A-Za-z0-9_]{3,})\b", text))
    return {item[:-2] if item.endswith("()") else item for item in identifiers}


def line_number_at(lines: list[str], index: int) -> int:
    return max(1, min(len(lines), index + 1))


def clean_title(line: str, finding_id: str) -> str:
    title = HEADING_RE.sub(r"\2", line).strip()
    title = re.sub(r"^\[?" + re.escape(finding_id) + r"\]?", "", title, flags=re.IGNORECASE)
    title = re.sub(r"^[\s:.\-\]\[]+", "", title)
    return title.strip() or finding_id


def fallback_title(section_lines: list[str], finding_id: str) -> str:
    for line in section_lines[:8]:
        stripped = line.strip()
        if not stripped:
            continue
        if FINDING_ID_RE.search(stripped):
            title = clean_title(stripped, finding_id)
            if title and title != finding_id:
                return title
        if len(stripped) < 160 and not stripped.startswith("|"):
            return stripped.strip("# ")
    return finding_id


def parse_findings(findings_file: Path) -> list[dict]:
    text = safe_read_text(findings_file, max_bytes=5_000_000)
    lines = text.splitlines()
    starts: list[tuple[int, str, str]] = []

    for index, line in enumerate(lines):
        stripped = line.strip()
        heading = HEADING_RE.match(stripped)
        id_match = FINDING_ID_RE.search(stripped)
        starts_like_section = bool(heading) or bool(re.match(r"^\[?(?:H|M|L|I|G|NC|QA|R|C|S|A)-?\d{1,4}\]?\b", stripped, re.I))
        if id_match and starts_like_section:
            found_id = display_id(id_match.group(1))
            starts.append((index, found_id, clean_title(stripped, id_match.group(1))))

    if not starts:
        starts = [(0, "F-1", "Finding 1")]

    findings = []
    seen: Counter[str] = Counter()
    for offset, (start_index, found_id, title) in enumerate(starts):
        end_index = starts[offset + 1][0] if offset + 1 < len(starts) else len(lines)
        section_lines = lines[start_index:end_index]
        content = "\n".join(section_lines).strip()
        if not content:
            continue

        normalized_id = canonical_id(found_id)
        seen[normalized_id] += 1
        unique_id = normalized_id if seen[normalized_id] == 1 else f"{normalized_id}.{seen[normalized_id]}"
        title = title if title and title != found_id else fallback_title(section_lines, found_id)
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        severity = normalized_id.split("-", 1)[0] if "-" in normalized_id else "UNKNOWN"
        tokens = sorted(tokenize(title + "\n" + content))
        identifiers = sorted(extract_identifiers(content))

        findings.append(
            {
                "id": display_id(found_id),
                "canonical_id": normalized_id,
                "unique_id": unique_id,
                "title": title,
                "severity": severity,
                "start_line": line_number_at(lines, start_index),
                "end_line": line_number_at(lines, max(start_index, end_index - 1)),
                "content_hash": content_hash,
                "content": content,
                "tokens": tokens,
                "identifiers": identifiers,
            }
        )
    return findings


def should_skip(path: Path, root: Path, include_deps: bool) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path
    parts = set(rel.parts)
    if include_deps:
        return bool(parts & (IGNORED_DIRS - {"node_modules"}))
    return bool(parts & IGNORED_DIRS)


def iter_repo_files(root: Path, include_deps: bool = False) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if should_skip(path, root, include_deps):
            continue
        yield path


def clean_comment(raw: str) -> str:
    text = raw
    text = re.sub(r"^\s*/\*\*?", "", text)
    text = re.sub(r"\*/\s*$", "", text)
    cleaned = []
    for line in text.splitlines():
        line = re.sub(r"^\s*(///|//|#|--|/\*+|\*)\s?", "", line)
        cleaned.append(line.rstrip())
    return "\n".join(cleaned).strip()


def extract_comments(text: str, suffix: str) -> str:
    blocks: list[str] = []
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

    for pattern in patterns:
        for match in re.finditer(pattern, text):
            comment = clean_comment(match.group(0).strip("\"'"))
            if len(comment) >= 20:
                blocks.append(comment)
    return "\n\n".join(blocks)


def headings(text: str) -> list[str]:
    values = []
    for line in text.splitlines():
        match = HEADING_RE.match(line.strip())
        if match:
            values.append(match.group(2).strip())
        if len(values) >= 12:
            break
    return values


def excerpt(text: str, max_chars: int = 500) -> str:
    compact = normalize_ws(text)
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def collect_local_doc(path: Path, source: str, repo_root: Path | None = None) -> dict | None:
    if path.stat().st_size > 2_000_000:
        return None
    text = safe_read_text(path)
    if path.suffix.lower() in DOC_EXTS:
        body = text
        kind = "document"
    elif path.suffix.lower() in SOURCE_EXTS:
        body = extract_comments(text, path.suffix.lower())
        kind = "source-comments"
        if not body:
            return None
    else:
        return None

    if not normalize_ws(body):
        return None

    display_path = str(path)
    if repo_root is not None:
        try:
            display_path = str(path.relative_to(repo_root))
        except ValueError:
            pass

    return {
        "source": source,
        "kind": kind,
        "path": str(path.resolve()),
        "display_path": display_path,
        "headings": headings(body),
        "excerpt": excerpt(body),
        "tokens": sorted(tokenize(body)),
        "identifiers": sorted(extract_identifiers(body)),
    }


def collect_docs(repo_root: Path, external_docs: list[str], include_deps: bool) -> list[dict]:
    docs: list[dict] = []
    seen_paths: set[str] = set()

    for path in iter_repo_files(repo_root, include_deps=include_deps):
        if path.suffix.lower() not in DOC_EXTS and path.suffix.lower() not in SOURCE_EXTS:
            continue
        doc = collect_local_doc(path, "repo", repo_root)
        if doc:
            seen_paths.add(doc["path"])
            docs.append(doc)

    for raw in external_docs:
        value = raw.strip()
        if not value:
            continue
        if value.startswith(("http://", "https://")):
            try:
                body = fetch_url(value)
            except Exception as exc:  # pragma: no cover - network varies
                docs.append(
                    {
                        "source": "external",
                        "kind": "url-error",
                        "path": value,
                        "display_path": value,
                        "headings": [],
                        "excerpt": f"Could not fetch URL during setup: {exc}",
                        "tokens": [],
                        "identifiers": [],
                    }
                )
                continue
            docs.append(
                {
                    "source": "external",
                    "kind": "url",
                    "path": value,
                    "display_path": value,
                    "headings": headings(body),
                    "excerpt": excerpt(body),
                    "tokens": sorted(tokenize(body)),
                    "identifiers": sorted(extract_identifiers(body)),
                    "fetched_text": body[:80_000],
                }
            )
            continue

        path = Path(value).expanduser().resolve()
        if path.is_dir():
            for child in path.rglob("*"):
                if not child.is_file() or child.suffix.lower() not in DOC_EXTS | SOURCE_EXTS:
                    continue
                doc = collect_local_doc(child, "external")
                if doc and doc["path"] not in seen_paths:
                    seen_paths.add(doc["path"])
                    docs.append(doc)
        elif path.is_file():
            doc = collect_local_doc(path, "external")
            if doc and doc["path"] not in seen_paths:
                seen_paths.add(doc["path"])
                docs.append(doc)
        else:
            docs.append(
                {
                    "source": "external",
                    "kind": "missing",
                    "path": value,
                    "display_path": value,
                    "headings": [],
                    "excerpt": "Path did not exist during setup.",
                    "tokens": [],
                    "identifiers": [],
                }
            )

    return docs


def context_around(text: str, start: int, end: int | None = None, max_chars: int = 420) -> str:
    if end is None:
        end = start
    left = max(0, start - max_chars // 2)
    right = min(len(text), end + max_chars // 2)
    prefix = "..." if left > 0 else ""
    suffix = "..." if right < len(text) else ""
    return prefix + normalize_ws(text[left:right]) + suffix


def line_containing_offset(text: str, offset: int) -> str:
    start = text.rfind("\n", 0, offset) + 1
    end = text.find("\n", offset)
    if end == -1:
        end = len(text)
    return text[start:end].strip()


def contract_label_from_line(line: str, address: str) -> str:
    cleaned = line.replace(address, "").replace(address.lower(), "").replace(address.upper(), "")
    cleaned = re.sub(r"[`'\"{},\[\]]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" :-=")
    if 3 <= len(cleaned) <= 120:
        return cleaned
    return ""


def chain_hits_in_text(text: str, source: str, display_path: str, max_hits_per_chain: int = 3) -> list[dict]:
    hits: list[dict] = []
    for chain, patterns in CHAIN_PATTERNS:
        chain_hits = 0
        seen_excerpts: set[str] = set()
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                chain_hits += 1
                excerpt_value = context_around(text, match.start(), match.end())
                if excerpt_value in seen_excerpts:
                    continue
                seen_excerpts.add(excerpt_value)
                hits.append(
                    {
                        "chain": chain,
                        "matched": match.group(0),
                        "source": source,
                        "display_path": display_path,
                        "excerpt": excerpt_value,
                    }
                )
                if chain_hits >= max_hits_per_chain:
                    break
            if chain_hits >= max_hits_per_chain:
                break
    return hits


def chain_names_in_text(text: str) -> list[str]:
    names = []
    for hit in chain_hits_in_text(text, "context", "context", max_hits_per_chain=1):
        if hit["chain"] not in names:
            names.append(hit["chain"])
    return names


def deployment_urls_in_text(text: str, max_urls: int = 80) -> list[str]:
    urls = []
    for match in URL_RE.finditer(text):
        url = match.group(0).rstrip(".,;")
        lowered = url.lower()
        if any(
            marker in lowered
            for marker in (
                "address",
                "blockscout",
                "contract",
                "deploy",
                "docs",
                "etherscan",
                "explorer",
                "github",
                "scan",
                "scope",
            )
        ):
            urls.append(url)
        if len(urls) >= max_urls:
            break
    return urls


def is_deployment_candidate(path: Path, repo_root: Path) -> bool:
    try:
        rel = str(path.relative_to(repo_root))
    except ValueError:
        rel = str(path)
    lowered = rel.lower()
    if path.suffix.lower() in DEPLOYMENT_EXTS and DEPLOYMENT_NAME_RE.search(lowered):
        return True
    if path.name.startswith(".env") or path.name in {"foundry.toml", "hardhat.config.ts", "hardhat.config.js"}:
        return True
    return False


def iter_deployment_sources(repo_root: Path, docs: list[dict], include_deps: bool) -> list[dict]:
    sources: list[dict] = []
    seen: set[str] = set()

    for doc in docs:
        path_value = doc["path"]
        key = f"doc:{path_value}"
        if key in seen:
            continue
        seen.add(key)
        if doc.get("fetched_text"):
            body = doc["fetched_text"]
        elif path_value.startswith(("http://", "https://")):
            body = doc.get("excerpt", "")
        else:
            path = Path(path_value)
            if not path.is_file():
                body = doc.get("excerpt", "")
            else:
                body = safe_read_text(path)
                if doc.get("kind") == "source-comments":
                    body = extract_comments(body, path.suffix.lower())
        if normalize_ws(body):
            sources.append(
                {
                    "source": doc.get("source", "repo"),
                    "kind": doc.get("kind", "document"),
                    "path": path_value,
                    "display_path": doc.get("display_path", path_value),
                    "text": body,
                }
            )

    for path in iter_repo_files(repo_root, include_deps=include_deps):
        if not is_deployment_candidate(path, repo_root):
            continue
        if path.stat().st_size > 1_000_000:
            continue
        key = f"file:{path.resolve()}"
        if key in seen:
            continue
        seen.add(key)
        try:
            body = safe_read_text(path)
        except Exception:
            continue
        try:
            display_path = str(path.relative_to(repo_root))
        except ValueError:
            display_path = str(path)
        if normalize_ws(body):
            sources.append(
                {
                    "source": "repo",
                    "kind": "deployment-candidate",
                    "path": str(path.resolve()),
                    "display_path": display_path,
                    "text": body,
                }
            )
    return sources


def add_address_record(records: dict, address_type: str, address: str, source: dict, start: int, end: int) -> None:
    comparable = address.lower() if address_type == "evm" else address
    if comparable in IGNORED_EVM_ADDRESSES:
        return
    key = (address_type, comparable)
    context = context_around(source["text"], start, end)
    record = records.setdefault(
        key,
        {
            "type": address_type,
            "address": address,
            "nearby_chains": [],
            "labels": [],
            "sources": [],
        },
    )

    for chain in chain_names_in_text(context):
        if chain not in record["nearby_chains"]:
            record["nearby_chains"].append(chain)

    label = contract_label_from_line(line_containing_offset(source["text"], start), address)
    if label and label not in record["labels"]:
        record["labels"].append(label)

    source_entry = {
        "display_path": source["display_path"],
        "source": source["source"],
        "kind": source["kind"],
        "excerpt": context,
    }
    if source_entry not in record["sources"]:
        record["sources"].append(source_entry)


def discover_deployment_context(repo_root: Path, docs: list[dict], external_docs: list[str], include_deps: bool) -> dict:
    sources = iter_deployment_sources(repo_root, docs, include_deps)
    chain_evidence: dict[str, list[dict]] = defaultdict(list)
    address_records: dict[tuple[str, str], dict] = {}
    candidate_urls: list[str] = []

    for source in sources:
        text = source["text"]
        for hit in chain_hits_in_text(text, source["source"], source["display_path"]):
            if len(chain_evidence[hit["chain"]]) < 10:
                chain_evidence[hit["chain"]].append(hit)
        for match in EVM_ADDRESS_RE.finditer(text):
            add_address_record(address_records, "evm", match.group(0), source, match.start(), match.end())
        for match in SOLANA_PROGRAM_RE.finditer(text):
            add_address_record(address_records, "solana-program", match.group(1), source, match.start(1), match.end(1))
        for url in deployment_urls_in_text(text):
            if url not in candidate_urls:
                candidate_urls.append(url)

    chain_rows = []
    for chain, evidence in chain_evidence.items():
        chain_rows.append(
            {
                "chain": chain,
                "evidence_count": len(evidence),
                "evidence": evidence[:5],
            }
        )
    chain_rows.sort(key=lambda item: (item["evidence_count"], item["chain"]), reverse=True)

    addresses = list(address_records.values())
    addresses.sort(key=lambda item: (len(item["sources"]), item["address"].lower()), reverse=True)
    for item in addresses:
        item["sources"] = item["sources"][:6]
        item["labels"] = item["labels"][:6]
        item["nearby_chains"] = item["nearby_chains"][:6]

    notes = [
        "Verify chains and addresses against official docs, bug bounty scope, and block explorers before relying on them.",
        "Address extraction is heuristic; token, oracle, proxy, implementation, and test addresses may appear together.",
    ]
    if external_docs:
        notes.append("External URLs and docs were included in deployment discovery.")
    else:
        notes.append("No external docs were supplied to the script; the agent should add official internet sources during setup.")
    if not chain_rows:
        notes.append("No chain evidence was discovered automatically.")
    if not addresses:
        notes.append("No contract or program addresses were discovered automatically.")

    return {
        "sources_scanned": len(sources),
        "chains": chain_rows,
        "addresses": addresses,
        "candidate_urls": candidate_urls[:80],
        "notes": notes,
    }


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def pair_score(left: dict, right: dict) -> tuple[float, list[str], list[str]]:
    left_tokens = set(left.get("tokens", []))
    right_tokens = set(right.get("tokens", []))
    left_identifiers = {item.lower() for item in left.get("identifiers", [])}
    right_identifiers = {item.lower() for item in right.get("identifiers", [])}

    token_score = jaccard(left_tokens, right_tokens)
    identifier_score = jaccard(left_identifiers, right_identifiers)
    title_score = jaccard(tokenize(left.get("title", "")), tokenize(right.get("title", "")))
    score = (0.62 * token_score) + (0.28 * identifier_score) + (0.10 * title_score)

    shared_terms = sorted((left_tokens & right_tokens), key=lambda item: (len(item), item), reverse=True)[:12]
    shared_identifiers = sorted(left_identifiers & right_identifiers)[:12]
    if len(shared_identifiers) >= 2:
        score += 0.08
    if title_score >= 0.45:
        score += 0.08
    return min(score, 1.0), shared_terms, shared_identifiers


def union_find(items: list[str]):
    parent = {item: item for item in items}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    return parent, find, union


def group_findings(findings: list[dict]) -> dict:
    ids = [finding["unique_id"] for finding in findings]
    parent, find, union = union_find(ids)
    duplicate_pairs = []
    related_pairs = []

    by_id = {finding["unique_id"]: finding for finding in findings}
    for index, left in enumerate(findings):
        for right in findings[index + 1 :]:
            score, shared_terms, shared_identifiers = pair_score(left, right)
            pair = {
                "left": left["unique_id"],
                "right": right["unique_id"],
                "score": round(score, 3),
                "shared_terms": shared_terms,
                "shared_identifiers": shared_identifiers,
            }
            if score >= 0.42:
                duplicate_pairs.append(pair)
                union(left["unique_id"], right["unique_id"])
            elif score >= 0.22 or len(shared_identifiers) >= 3:
                related_pairs.append(pair)
                union(left["unique_id"], right["unique_id"])

    clusters: defaultdict[str, list[str]] = defaultdict(list)
    for item in ids:
        clusters[find(item)].append(item)

    related_groups = []
    standalone = []
    for group_ids in clusters.values():
        ordered = sorted(group_ids, key=lambda item: ids.index(item))
        if len(ordered) == 1:
            standalone.append(ordered[0])
            continue
        common_terms = set(by_id[ordered[0]].get("tokens", []))
        common_identifiers = {item.lower() for item in by_id[ordered[0]].get("identifiers", [])}
        for item in ordered[1:]:
            common_terms &= set(by_id[item].get("tokens", []))
            common_identifiers &= {identifier.lower() for identifier in by_id[item].get("identifiers", [])}
        related_groups.append(
            {
                "ids": ordered,
                "common_terms": sorted(common_terms, key=lambda term: (len(term), term), reverse=True)[:12],
                "common_identifiers": sorted(common_identifiers)[:12],
            }
        )

    duplicate_groups = []
    duplicate_parent, duplicate_find, duplicate_union = union_find(ids)
    for pair in duplicate_pairs:
        duplicate_union(pair["left"], pair["right"])
    duplicate_clusters: defaultdict[str, list[str]] = defaultdict(list)
    for item in ids:
        duplicate_clusters[duplicate_find(item)].append(item)
    for group_ids in duplicate_clusters.values():
        if len(group_ids) > 1:
            duplicate_groups.append(sorted(group_ids, key=lambda item: ids.index(item)))

    return {
        "duplicate_groups": duplicate_groups,
        "related_groups": related_groups,
        "standalone": standalone,
        "duplicate_pairs": duplicate_pairs,
        "related_pairs": related_pairs,
    }


def score_doc_for_finding(doc: dict, finding: dict) -> tuple[float, list[str], list[str]]:
    doc_tokens = set(doc.get("tokens", []))
    doc_identifiers = {item.lower() for item in doc.get("identifiers", [])}
    finding_tokens = set(finding.get("tokens", []))
    finding_identifiers = {item.lower() for item in finding.get("identifiers", [])}
    matched_terms = sorted(finding_tokens & doc_tokens)[:16]
    matched_identifiers = sorted(finding_identifiers & doc_identifiers)[:16]
    if not matched_terms and not matched_identifiers:
        return 0.0, [], []
    score = (len(matched_terms) / math.sqrt(max(1, len(finding_tokens)))) + (2.0 * len(matched_identifiers))
    return score, matched_terms, matched_identifiers


def add_doc_hits(findings: list[dict], docs: list[dict]) -> None:
    for finding in findings:
        hits = []
        for doc in docs:
            score, matched_terms, matched_identifiers = score_doc_for_finding(doc, finding)
            if score <= 0:
                continue
            hits.append(
                {
                    "path": doc["path"],
                    "display_path": doc["display_path"],
                    "source": doc["source"],
                    "kind": doc["kind"],
                    "score": round(score, 3),
                    "matched_terms": matched_terms,
                    "matched_identifiers": matched_identifiers,
                    "excerpt": doc["excerpt"],
                }
            )
        finding["doc_hits"] = sorted(hits, key=lambda item: item["score"], reverse=True)[:8]


def write_related_markdown(path: Path, context: dict) -> None:
    findings_by_id = {finding["unique_id"]: finding for finding in context["findings"]}
    lines = [
        "# Related Findings",
        "",
        f"Generated: {context['generated_at']}",
        f"Findings file: `{context['findings_file']}`",
        f"Repo root: `{context['repo_root']}`",
        "",
        "This file is a setup artifact for triage. Treat groups as candidates and revise them with code-aware judgment before making final calls.",
        "",
    ]

    duplicate_groups = context["groups"]["duplicate_groups"]
    lines.append("## Duplicate-like Groups")
    lines.append("")
    if duplicate_groups:
        for index, group in enumerate(duplicate_groups, 1):
            lines.append(f"### D{index}")
            for item in group:
                finding = findings_by_id[item]
                lines.append(f"- `{finding['id']}` {finding['title']}")
            lines.append("")
    else:
        lines.append("No high-similarity duplicate groups detected by the setup pass.")
        lines.append("")

    lines.append("## Related Groups")
    lines.append("")
    related_groups = context["groups"]["related_groups"]
    if related_groups:
        for index, group in enumerate(related_groups, 1):
            lines.append(f"### R{index}")
            if group["common_terms"] or group["common_identifiers"]:
                terms = ", ".join(f"`{term}`" for term in group["common_terms"][:8])
                identifiers = ", ".join(f"`{term}`" for term in group["common_identifiers"][:8])
                evidence = ", ".join(part for part in (terms, identifiers) if part)
                lines.append(f"Shared signals: {evidence}")
                lines.append("")
            for item in group["ids"]:
                finding = findings_by_id[item]
                lines.append(f"- `{finding['id']}` {finding['title']}")
            lines.append("")
    else:
        lines.append("No related groups detected by the setup pass.")
        lines.append("")

    lines.append("## Standalone Findings")
    lines.append("")
    standalone = context["groups"]["standalone"]
    if standalone:
        for item in standalone:
            finding = findings_by_id[item]
            lines.append(f"- `{finding['id']}` {finding['title']}")
    else:
        lines.append("No standalone findings detected.")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_docs_index(path: Path, context: dict) -> None:
    lines = [
        "# Triage Documentation Index",
        "",
        f"Generated: {context['generated_at']}",
        "",
        "## Inputs",
        "",
        f"- Repo root: `{context['repo_root']}`",
        f"- Findings file: `{context['findings_file']}`",
    ]
    if context["external_docs"]:
        for doc in context["external_docs"]:
            lines.append(f"- External docs: `{doc}`")
    else:
        lines.append("- External docs: none provided")
    lines.extend(["", "## Indexed Documentation", ""])

    if not context["docs"]:
        lines.append("No docs, NatSpec, or comment blocks were indexed.")
    else:
        for doc in context["docs"]:
            lines.append(f"- `{doc['display_path']}` ({doc['source']}, {doc['kind']})")
            if doc.get("headings"):
                lines.append(f"  - headings: {', '.join(doc['headings'][:5])}")
    lines.extend(["", "## Top Documentation Hits By Finding", ""])
    for finding in context["findings"]:
        lines.append(f"### `{finding['id']}` {finding['title']}")
        hits = finding.get("doc_hits", [])
        if not hits:
            lines.append("- No doc hits found.")
        for hit in hits[:5]:
            labels = []
            if hit["matched_identifiers"]:
                labels.append("identifiers: " + ", ".join(f"`{value}`" for value in hit["matched_identifiers"][:5]))
            if hit["matched_terms"]:
                labels.append("terms: " + ", ".join(f"`{value}`" for value in hit["matched_terms"][:5]))
            suffix = f" ({'; '.join(labels)})" if labels else ""
            lines.append(f"- `{hit['display_path']}` score {hit['score']}{suffix}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_deployment_context(path: Path, context: dict) -> None:
    deployment = context["deployment"]
    lines = [
        "# Deployment Context",
        "",
        f"Generated: {context['generated_at']}",
        f"Repo root: `{context['repo_root']}`",
        f"Findings file: `{context['findings_file']}`",
    ]
    if context.get("protocol_name"):
        lines.append(f"Protocol name: `{context['protocol_name']}`")
    lines.extend(
        [
            "",
            "This file is a setup artifact for bug-bounty triage. Treat it as evidence to verify, not as final truth.",
            "",
            "## Discovery Notes",
            "",
        ]
    )
    for note in deployment.get("notes", []):
        lines.append(f"- {note}")
    lines.append(f"- Sources scanned by the script: {deployment.get('sources_scanned', 0)}")

    lines.extend(["", "## Likely Chains", ""])
    chains = deployment.get("chains", [])
    if not chains:
        lines.append("No chain evidence was discovered automatically.")
    for item in chains:
        lines.append(f"### {item['chain']}")
        lines.append(f"Evidence count: {item['evidence_count']}")
        lines.append("")
        for evidence in item.get("evidence", [])[:5]:
            lines.append(f"- `{evidence['display_path']}` ({evidence['source']}, matched `{evidence['matched']}`)")
            if evidence.get("excerpt"):
                lines.append(f"  - {evidence['excerpt']}")
        lines.append("")

    lines.extend(["", "## Candidate Contract Addresses", ""])
    addresses = deployment.get("addresses", [])
    if not addresses:
        lines.append("No contract or program addresses were discovered automatically.")
    for item in addresses:
        nearby = ", ".join(item.get("nearby_chains", [])) or "unknown nearby chain"
        labels = ", ".join(f"`{label}`" for label in item.get("labels", [])[:4])
        lines.append(f"### `{item['address']}`")
        lines.append(f"- Type: {item['type']}")
        lines.append(f"- Nearby chain evidence: {nearby}")
        if labels:
            lines.append(f"- Labels: {labels}")
        lines.append("- Sources:")
        for source in item.get("sources", [])[:6]:
            lines.append(f"  - `{source['display_path']}` ({source['source']}, {source['kind']})")
            if source.get("excerpt"):
                lines.append(f"    - {source['excerpt']}")
        lines.append("")

    lines.extend(["", "## Candidate Deployment URLs", ""])
    urls = deployment.get("candidate_urls", [])
    if not urls:
        lines.append("No deployment-related URLs were discovered automatically.")
    for url in urls:
        lines.append(f"- {url}")

    lines.extend(
        [
            "",
            "## Manual Verification Checklist",
            "",
            "- Confirm the bug bounty scope and official deployment pages.",
            "- Confirm chain IDs, proxy addresses, implementation addresses, and upgrade/admin roles.",
            "- Confirm relevant current config through read-only contract calls or block explorers.",
            "- Record TVL, balances, caps, paused state, whitelists, oracle configuration, and role holders needed by each finding.",
        ]
    )

    path.write_text("\n".join(lines), encoding="utf-8")


def build_context(args: argparse.Namespace) -> dict:
    repo_root = Path(args.repo).expanduser().resolve()
    findings_file = Path(args.findings).expanduser().resolve()
    if not repo_root.is_dir():
        raise SystemExit(f"Repo root is not a directory: {repo_root}")
    if not findings_file.is_file():
        raise SystemExit(f"Findings file does not exist: {findings_file}")

    output_dir = Path(args.output).expanduser().resolve() if args.output else findings_file.parent / "bb-triage-helper-output"
    output_dir.mkdir(parents=True, exist_ok=True)

    external_docs = args.external_doc or []
    findings = parse_findings(findings_file)
    docs = collect_docs(repo_root, external_docs, include_deps=args.include_deps)
    add_doc_hits(findings, docs)
    groups = group_findings(findings)
    deployment = discover_deployment_context(repo_root, docs, external_docs, include_deps=args.include_deps)

    return {
        "version": VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "helper": HELPER_NAME,
        "protocol_name": args.protocol_name or "",
        "repo_root": str(repo_root),
        "findings_file": str(findings_file),
        "external_docs": external_docs,
        "output_dir": str(output_dir),
        "findings_count": len(findings),
        "docs_count": len(docs),
        "findings": findings,
        "docs": docs,
        "groups": groups,
        "deployment": deployment,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Set up bug-bounty triage artifacts from a repo and findings.md.")
    parser.add_argument("--repo", required=True, help="Path to the repository under triage.")
    parser.add_argument("--findings", required=True, help="Path to the markdown findings file.")
    parser.add_argument("--protocol-name", help="Optional protocol/project name for deployment discovery notes.")
    parser.add_argument(
        "--external-doc",
        action="append",
        default=[],
        help="Optional external documentation path, directory, or URL. Repeat for multiple inputs.",
    )
    parser.add_argument("--output", help="Output directory. Defaults to findings-file sibling bb-triage-helper-output/.")
    parser.add_argument("--include-deps", action="store_true", help="Include dependency directories during indexing.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    context = build_context(args)
    output_dir = Path(context["output_dir"])

    context_path = output_dir / "triage-context.json"
    related_path = output_dir / "related-findings.md"
    docs_path = output_dir / "docs-index.md"
    deployment_path = output_dir / "deployment-context.md"

    context_path.write_text(json.dumps(context, indent=2), encoding="utf-8")
    write_related_markdown(related_path, context)
    write_docs_index(docs_path, context)
    write_deployment_context(deployment_path, context)

    print(f"Indexed {context['findings_count']} findings and {context['docs_count']} documentation sources.")
    print(
        f"Found {len(context['deployment']['chains'])} candidate chains and "
        f"{len(context['deployment']['addresses'])} candidate addresses."
    )
    print(f"Wrote context: {context_path}")
    print(f"Wrote related findings: {related_path}")
    print(f"Wrote docs index: {docs_path}")
    print(f"Wrote deployment context: {deployment_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
