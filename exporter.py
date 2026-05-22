"""
EU Financial Services Level 1 Legislation Exporter
====================================================

Two-phase approach:
  Phase 1 — SPARQL: fetch all in-force Level 1 Regulations & Directives
             (EP+Council or Council-only acts) from CELLAR, identified by
             title pattern rather than EuroVoc (which is patchy).
  Phase 2 — Python: classify each act as financial-services relevant using
             a comprehensive keyword list covering every major regulatory
             domain.
  Safety net — a hardcoded CELEX seed list ensures the most critical acts
               are always included, regardless of SPARQL/triplestore quirks.
"""

import os
import time
import requests
import pandas as pd
import threading
import re
import traceback
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import webbrowser


def _ts() -> str:
    return datetime.utcnow().isoformat()


def debug_print(msg: str) -> None:
    tname = threading.current_thread().name
    print(f"[DEBUG {_ts()}][{tname}] {msg}", flush=True)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SPARQL_ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"
OUTPUT_DIR = "output"
LEVEL1_TXT_FILE = os.path.join(OUTPUT_DIR, "eu_financial_legislation_level1.txt")
LEVEL1_CSV_FILE = os.path.join(OUTPUT_DIR, "eu_financial_legislation_level1.csv")
LEVEL2_TXT_FILE = os.path.join(OUTPUT_DIR, "eu_financial_legislation_level2.txt")
LEVEL2_CSV_FILE = os.path.join(OUTPUT_DIR, "eu_financial_legislation_level2.csv")
COMBINED_TXT_FILE = os.path.join(OUTPUT_DIR, "eu_financial_legislation_combined.txt")
COMBINED_CSV_FILE = os.path.join(OUTPUT_DIR, "eu_financial_legislation_combined.csv")

ALL_COLUMNS = [
    "celex",
    "level",
    "type",
    "level2_type",
    "category",
    "parent_framework",
    "parent_celex",
    "title",
    "date",
    "url",
]

# Maximum acts to fetch per query page; CELLAR returns at most 10 000 rows
# per request.  We page until exhausted.
PAGE_SIZE = 1000

# ---------------------------------------------------------------------------
# HARDCODED SEED LIST
# ---------------------------------------------------------------------------
# Acts that MUST appear in the output regardless of what SPARQL returns.
# Keyed by CELEX → human-readable title.  This is the safety net for acts
# that are in-force but whose CELLAR metadata may be inconsistent.
# ---------------------------------------------------------------------------

SEED_CELEX: dict[str, str] = {
    # --- Investment services & markets ---
    "32014L0065": "Directive 2014/65/EU — MiFID II (Markets in Financial Instruments)",
    "32014R0600":  "Regulation (EU) No 600/2014 — MiFIR",
    # --- Capital requirements / banking ---
    "32013R0575":  "Regulation (EU) No 575/2013 — CRR (Capital Requirements Regulation)",
    "32013L0036":  "Directive 2013/36/EU — CRD IV (Capital Requirements Directive)",
    "32019R0876":  "Regulation (EU) 2019/876 — CRR II",
    "32019L0878":  "Directive (EU) 2019/878 — CRD V",
    "32024R1623":  "Regulation (EU) 2024/1623 — CRR III",
    "32024L1619":  "Directive (EU) 2024/1619 — CRD VI",
    # --- AML / CFT ---
    "32015L0849":  "Directive (EU) 2015/849 — 4AMLD",
    "32018L0843":  "Directive (EU) 2018/843 — 5AMLD",
    "32024R1624":  "Regulation (EU) 2024/1624 — AML Regulation (AMLR)",
    "32024L1640":  "Directive (EU) 2024/1640 — 6AMLD",
    "32024R1620":  "Regulation (EU) 2024/1620 — AMLA (AML Authority)",
    # --- Crypto-assets ---
    "32023R1114":  "Regulation (EU) 2023/1114 — MiCAR (Markets in Crypto-Assets)",
    "32022R0858":  "Regulation (EU) 2022/858 — DLT Pilot Regime",
    # --- Digital operational resilience ---
    "32022R2554":  "Regulation (EU) 2022/2554 — DORA",
    "32022L2556":  "Directive (EU) 2022/2556 — DORA amending Directive",
    # --- UCITS / funds ---
    "32009L0065":  "Directive 2009/65/EC — UCITS IV",
    "32014L0091":  "Directive 2014/91/EU — UCITS V",
    # --- Alternative investment funds ---
    "32011L0061":  "Directive 2011/61/EU — AIFMD",
    "32024L0927":  "Directive (EU) 2024/927 — AIFMD II",
    # --- Insurance ---
    "32009L0138":  "Directive 2009/138/EC — Solvency II",
    "32025L0002":  "Directive (EU) 2025/2 — Solvency II omnibus revision",
    "32016L0097":  "Directive (EU) 2016/97 — IDD (Insurance Distribution)",
    # --- Occupational pensions ---
    "32016L2341":  "Directive (EU) 2016/2341 — IORP II",
    # --- OTC derivatives / clearing ---
    "32012R0648":  "Regulation (EU) No 648/2012 — EMIR",
    "32019R0834":  "Regulation (EU) 2019/834 — EMIR Refit",
    "32021R0023":  "Regulation (EU) 2021/23 — CCP Recovery and Resolution",
    # --- Investment firms ---
    "32019R2033":  "Regulation (EU) 2019/2033 — IFR (Investment Firms Regulation)",
    "32019L2034":  "Directive (EU) 2019/2034 — IFD (Investment Firms Directive)",
    # --- Market abuse ---
    "32014R0596":  "Regulation (EU) No 596/2014 — MAR (Market Abuse)",
    # --- Prospectus ---
    "32017R1129":  "Regulation (EU) 2017/1129 — Prospectus Regulation",
    # --- Transparency / shareholder rights ---
    "32004L0109":  "Directive 2004/109/EC — Transparency Directive",
    "32013L0050":  "Directive 2013/50/EU — Transparency Directive amendment",
    "32017L0828":  "Directive (EU) 2017/828 — SRD II (Shareholder Rights)",
    # --- Short selling ---
    "32012R0236":  "Regulation (EU) No 236/2012 — Short Selling Regulation",
    # --- Central securities depositories ---
    "32014R0909":  "Regulation (EU) No 909/2014 — CSDR",
    # --- Benchmarks ---
    "32016R1011":  "Regulation (EU) 2016/1011 — Benchmarks Regulation (BMR)",
    # --- Securities financing transactions ---
    "32015R2365":  "Regulation (EU) 2015/2365 — SFTR",
    # --- Securitisation ---
    "32017R2402":  "Regulation (EU) 2017/2402 — Securitisation Regulation",
    # --- Money market funds ---
    "32017R1131":  "Regulation (EU) 2017/1131 — MMF Regulation",
    # --- Payment services ---
    "32015L2366":  "Directive (EU) 2015/2366 — PSD2",
    "32024L2853":  "Directive (EU) 2024/2853 — PSD3",
    "32024R1814":  "Regulation (EU) 2024/1814 — PSR (Payment Services Regulation)",
    # --- E-money ---
    "32009L0110":  "Directive 2009/110/EC — EMD2 (Electronic Money)",
    # --- Payment accounts ---
    "32014L0092":  "Directive 2014/92/EU — PAD (Payment Accounts)",
    # --- Wire transfers ---
    "32015R0847":  "Regulation (EU) 2015/847 — Wire Transfer Regulation",
    "32023R1113":  "Regulation (EU) 2023/1113 — TFR (Transfer of Funds Regulation)",
    # --- Deposit guarantee schemes ---
    "32014L0049":  "Directive 2014/49/EU — DGSD (Deposit Guarantee Schemes)",
    # --- Bank recovery & resolution ---
    "32014L0059":  "Directive 2014/59/EU — BRRD",
    "32019L0879":  "Directive (EU) 2019/879 — BRRD II",
    "32014R0806":  "Regulation (EU) No 806/2014 — SRMR (Single Resolution Mechanism)",
    "32026R0808":  "Regulation (EU) 2026/808 — SRMR III",
    # --- Single supervisory mechanism ---
    "32013R1024":  "Regulation (EU) No 1024/2013 — SSM Regulation",
    # --- ESA / supervisory architecture ---
    "32010R1093":  "Regulation (EU) No 1093/2010 — EBA Regulation",
    "32010R1094":  "Regulation (EU) No 1094/2010 — EIOPA Regulation",
    "32010R1095":  "Regulation (EU) No 1095/2010 — ESMA Regulation",
    "32010R1092":  "Regulation (EU) No 1092/2010 — ESRB Regulation",
    "32019R2175":  "Regulation (EU) 2019/2175 — ESA Omnibus Review",
    # --- Sustainable finance ---
    "32019R2088":  "Regulation (EU) 2019/2088 — SFDR (Sustainable Finance Disclosure)",
    "32020R0852":  "Regulation (EU) 2020/852 — Taxonomy Regulation",
    "32023R2631":  "Regulation (EU) 2023/2631 — European Green Bond Standard",
    # --- Packaged retail products ---
    "32014R1286":  "Regulation (EU) No 1286/2014 — PRIIPs",
    # --- Financial conglomerates ---
    "32002L0087":  "Directive 2002/87/EC — Financial Conglomerates Directive (FICOD)",
    # --- Credit rating agencies ---
    "32009R1060":  "Regulation (EU) No 1060/2009 — CRA Regulation",
    # --- Covered bonds ---
    "32019L2162":  "Directive (EU) 2019/2162 — Covered Bonds Directive",
    "32019R2160":  "Regulation (EU) 2019/2160 — Covered Bonds Regulation (CRR amendment)",
    # --- Mortgage credit ---
    "32014L0017":  "Directive 2014/17/EU — Mortgage Credit Directive (MCD)",
    # --- Consumer credit ---
    "32023L2225":  "Directive (EU) 2023/2225 — Consumer Credit Directive II (CCD II)",
    # --- Crowdfunding ---
    "32020R1503":  "Regulation (EU) 2020/1503 — Crowdfunding Regulation",
    # --- Central counterparty / clearing ---
    "32024R2987":  "Regulation (EU) 2024/2987 — EMIR 3 (clearing markets)",
    # --- Conglomerate / supervision ---
    "32013L0036":  "Directive 2013/36/EU — CRD IV",
}


# ---------------------------------------------------------------------------
# Phase 2 — Python-side financial services keyword classifier
# ---------------------------------------------------------------------------
# Match against the lower-cased title.  Two tiers:
#   STRONG_KEYWORDS: high-precision terms → include if any match
#   BROAD_KEYWORDS:  broader terms → include if any match (may need review)
# ---------------------------------------------------------------------------

STRONG_KEYWORDS: list[str] = [
    # Investment services & trading venues
    "markets in financial instruments",
    "mifid",
    "mifir",
    "investment firm",
    "investment service",
    "systematic internaliser",
    "trading venue",
    "regulated market",
    "multilateral trading",
    "organised trading",
    # Capital requirements / banking
    "capital requirements",
    "capital adequacy",
    "credit institution",
    "own funds",
    "leverage ratio",
    "liquidity coverage",
    "net stable funding",
    "pillar",
    # AML / CFT
    "anti-money laundering",
    "money laundering",
    "terrorist financing",
    "financial intelligence unit",
    "beneficial owner",
    "politically exposed",
    # Crypto / DLT
    "crypto-asset",
    "crypto asset",
    "distributed ledger",
    "virtual asset",
    "electronic money token",
    "asset-referenced token",
    # Insurance & reinsurance
    "insurance undertaking",
    "reinsurance",
    "solvency",
    "solvency ii",
    "insurance distribution",
    "insurance mediation",
    # Occupational pensions
    "occupational pension",
    "institution for occupational retirement",
    "iorp",
    # OTC derivatives / clearing / CCP
    "over-the-counter derivative",
    "central counterparty",
    "trade repository",
    "margin requirement",
    "clearing obligation",
    # Market abuse
    "market abuse",
    "insider dealing",
    "market manipulation",
    "inside information",
    # Prospectus / securities offerings
    "prospectus",
    "public offer",
    # Short selling
    "short selling",
    "credit default swap",
    # CSDR / settlement
    "central securities depository",
    "securities settlement",
    # Benchmarks
    "benchmark administrator",
    "financial benchmark",
    # SFTR
    "securities financing transaction",
    # Securitisation
    "securitisation",
    "asset-backed",
    "simple, transparent and standardised",
    # MMF
    "money market fund",
    # Payment services
    "payment service",
    "payment institution",
    "payment account",
    "payment system",
    "payment transaction",
    # E-money
    "electronic money institution",
    "e-money institution",
    # Wire transfer / fund transfer
    "wire transfer",
    "transfer of funds",
    # DGS
    "deposit guarantee",
    "deposit protection",
    # BRRD / resolution
    "bank recovery",
    "bank resolution",
    "resolution authority",
    "bail-in",
    "write down",
    "single resolution",
    # SSM / banking union
    "single supervisory mechanism",
    "prudential supervision",
    "supervisory review",
    "significant institution",
    # ESAs
    "european banking authority",
    "european insurance and occupational pensions authority",
    "european securities and markets authority",
    "european systemic risk board",
    # DORA
    "digital operational resilience",
    "ict risk",
    # Sustainable finance
    "sustainable finance",
    "sustainability-related disclosure",
    "sustainable investment",
    "taxonomy",
    "green bond",
    "esg",
    # PRIIPs / packaged products
    "packaged retail",
    "key information document",
    "priips",
    # Covered bonds
    "covered bond",
    # Mortgage / consumer credit
    "mortgage credit",
    "consumer credit",
    # Crowdfunding
    "crowdfunding service provider",
    # Shareholder rights
    "shareholder right",
    "say on pay",
    # Financial conglomerates
    "financial conglomerate",
    # Credit rating agencies
    "credit rating agency",
    "credit rating",
    # Investment funds (generic)
    "undertakings for collective investment",
    "ucits",
    "alternative investment fund",
    "aifm",
    # Investor compensation
    "investor compensation",
    "compensation scheme",
]

BROAD_KEYWORDS: list[str] = [
    # May match non-financial acts — kept as fallback
    "financial instrument",
    "financial market",
    "financial sector",
    "financial services",
    "financial stability",
    "financial system",
    "financial supervision",
    "capital market",
    "banking",
    "payment",
    "clearing",
    "settlement",
    "securities",
    "derivatives",
    "systemic risk",
    "resolution fund",
]

CATEGORIES: list[str] = [
    "Banking & Prudential",
    "Capital Markets & Investment Services",
    "Asset Management & Funds",
    "Payments & E-Money",
    "AML / Financial Crime",
    "Insurance",
    "Sustainable Finance / ESG",
    "Crypto & Digital Finance",
    "Financial Market Infrastructure",
    "Consumer Protection",
    "Financial Reporting & Audit",
    "Supervisory Architecture",
]

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Banking & Prudential": [
        "crr",
        "crd",
        "brrd",
        "dgsd",
        "deposit guarantee",
        "bank recovery",
        "resolution authority",
        "single resolution",
        "resolution mechanism",
        "single supervisory mechanism",
        "ssm",
        "capital requirements",
        "prudential supervision",
        "own funds",
        "leverage ratio",
        "liquidity coverage",
        "net stable funding",
        "credit institution",
        "credit rating agency",
    ],
    "Capital Markets & Investment Services": [
        "mifid",
        "mifir",
        "markets in financial instruments",
        "investment firm",
        "investment service",
        "trading venue",
        "regulated market",
        "multilateral trading",
        "organised trading",
        "prospectus",
        "short selling",
        "benchmark",
        "market abuse",
        "transparency directive",
        "transparency",
        "public offer",
    ],
    "Asset Management & Funds": [
        "ucits",
        "aifmd",
        "eltif",
        "asset management",
        "alternative investment fund",
        "money market fund",
        "securitisation",
        "covered bond",
        "investment fund",
        "packaged retail",
    ],
    "Payments & E-Money": [
        "payment service",
        "payment institution",
        "payment account",
        "payment system",
        "payment transaction",
        "electronic money",
        "e-money",
        "psd",
        "psd2",
        "psd3",
        "wire transfer",
        "transfer of funds",
    ],
    "AML / Financial Crime": [
        "anti-money laundering",
        "money laundering",
        "terrorist financing",
        "financial intelligence unit",
        "beneficial owner",
        "politically exposed",
        "amld",
        "amlr",
        "transfer of funds",
        "wire transfer",
    ],
    "Insurance": [
        "solvency ii",
        "insurance distribution",
        "insurance mediation",
        "solvency",
        "insurance undertaking",
        "reinsurance",
        "idd",
    ],
    "Sustainable Finance / ESG": [
        "sustainable finance",
        "sustainability-related disclosure",
        "taxonomy",
        "green bond",
        "esg",
        "sfdr",
        "sustainable investment",
    ],
    "Crypto & Digital Finance": [
        "micar",
        "mica",
        "dora",
        "digital operational resilience",
        "crypto-asset",
        "crypto asset",
        "distributed ledger",
        "virtual asset",
        "electronic money token",
        "asset-referenced token",
        "dlt pilot",
    ],
    "Financial Market Infrastructure": [
        "emir",
        "csdr",
        "sftr",
        "central securities depository",
        "securities settlement",
        "trade repository",
        "clearing obligation",
        "margin requirement",
        "central counterparty",
        "ccp",
        "securities financing transaction",
    ],
    "Consumer Protection": [
        "priips",
        "mortgage credit",
        "consumer credit",
        "compensation scheme",
        "investor compensation",
        "key information document",
        "retail",
    ],
    "Financial Reporting & Audit": [
        "ifrs",
        "audit",
        "transparency",
        "reporting",
        "accounting",
        "disclosure",
    ],
    "Supervisory Architecture": [
        "esma",
        "eba",
        "eiopa",
        "esrb",
        "ssm",
        "single supervisory mechanism",
        "european banking authority",
        "european securities and markets authority",
        "european insurance and occupational pensions authority",
        "european systemic risk board",
        "supervisory authority",
    ],
}

CATEGORY_COLORS: dict[str, str] = {
    "Banking & Prudential": "#d9eaf7",
    "Capital Markets & Investment Services": "#dff2d8",
    "Asset Management & Funds": "#fff4cc",
    "Payments & E-Money": "#d9f2e6",
    "AML / Financial Crime": "#f9d6d5",
    "Insurance": "#e8d9f7",
    "Sustainable Finance / ESG": "#e6f0d9",
    "Crypto & Digital Finance": "#e8f0fa",
    "Financial Market Infrastructure": "#ddebf7",
    "Consumer Protection": "#fff1d6",
    "Financial Reporting & Audit": "#e9e9f2",
    "Supervisory Architecture": "#dceef8",
}


def category_for_legislation(title: str, celex: str) -> str:
    """Return the best matching financial-services category for a title."""
    t = title.lower()
    for category in CATEGORIES:
        for kw in CATEGORY_KEYWORDS.get(category, []):
            if kw in t:
                return category

    # Fall back to CELEX-based hints for specific acts.
    if celex.startswith("320"):  # CELEX prefixes are mostly EU acts
        if celex[5:6] == "R" and "24" in celex:
            return "Banking & Prudential"

    return "Banking & Prudential"


def assign_category(rows: list[dict]) -> None:
    for row in rows:
        row["category"] = category_for_legislation(row["title"], row["celex"])


def filter_by_category(rows: list[dict], category: str) -> list[dict]:
    if category == "All Categories":
        return rows
    return [r for r in rows if r.get("category") == category]


def is_financial_services(title: str) -> bool:
    """Return True if the title relates to EU financial services legislation."""
    t = title.lower()
    for kw in STRONG_KEYWORDS:
        if kw in t:
            return True
    # BROAD keywords only apply if at least one other context word is present
    context = any(w in t for w in ["directive", "regulation", "framework"])
    if context:
        for kw in BROAD_KEYWORDS:
            if kw in t:
                return True
    return False


# ---------------------------------------------------------------------------
# Level 2 discovery + parent-linkage
# ---------------------------------------------------------------------------

STOP_WORDS: set[str] = {
    "the", "and", "of", "in", "for", "with", "to", "a", "an",
    "by", "eu", "european", "parliament", "council", "union",
    "directive", "regulation", "implementing", "delegated", "technical",
    "standard", "supplementing", "amending", "act", "legislation",
    "europe", "commission",
}


def extract_significant_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for token in re.split(r"\W+", text or ""):
        normalized = token.strip().lower()
        if not normalized:
            continue
        if len(normalized) < 4:
            continue
        if normalized.isdigit():
            continue
        if normalized in STOP_WORDS:
            continue
        tokens.append(normalized)
    return tokens


def build_short_name_from_title(title: str) -> str:
    if not title:
        return ""

    if "—" in title:
        candidate = title.split("—")[-1].strip()
        if len(candidate) >= 10:
            return candidate

    if " - " in title:
        candidate = title.split(" - ")[-1].strip()
        if len(candidate) >= 10:
            return candidate

    for separator in [
        " of the European Parliament and of the Council",
        " of the European Parliament and of the",
        " of the European Parliament",
        " of the Council",
        " of the European Union",
    ]:
        if separator in title:
            return title.split(separator)[0].strip()

    if "—" in title:
        return title.split("—")[0].strip()

    if len(title) <= 60:
        return title.strip()

    return title[:60].strip()


def build_level1_frameworks(rows: list[dict]) -> dict:
    """Build a registry of Level 1 frameworks keyed by CELEX.

    Each entry contains a short_name and category. The short_name is
    derived from the title (best-effort) or taken from the seed list.
    """
    frameworks: dict = {}
    for r in rows:
        celex = r.get("celex")
        title = r.get("title", "")
        category = r.get("category", "")
        short = SEED_CELEX.get(celex)
        if short:
            short_name = short.split("—")[0].strip()
        else:
            short_name = build_short_name_from_title(title)
        frameworks[celex] = {"short_name": short_name, "category": category}
    return frameworks


def detect_level2_type(title: str) -> str:
    t = title.lower()
    if "delegated regulation" in t:
        return "Delegated Regulation"
    if "implementing regulation" in t:
        return "Implementing Regulation"
    if "delegated directive" in t:
        return "Delegated Directive"
    if "implementing directive" in t:
        return "Implementing Directive"
    if "regulatory technical standard" in t or "rts" in t:
        return "RTS"
    if "implementing technical standard" in t or "its" in t:
        return "ITS"
    # fallback to simple heuristics
    if "delegated" in t:
        return "Delegated Regulation"
    if "implementing" in t:
        return "Implementing Regulation"
    return "Other"


def build_level2_title_match_clauses(parent_celex: str, parent_short: str) -> str:
    esc_celex = parent_celex or ""
    short_tokens = extract_significant_tokens(parent_short or "")

    parent_patterns: list[str] = []
    try:
        if esc_celex and len(esc_celex) >= 11:
            parent_year = esc_celex[1:5]
            num_raw = esc_celex[6:]
            num = str(int(num_raw))
            parent_patterns.extend([
                f"{parent_year}/{num}",
                f"{parent_year}/{num_raw}",
                f"{parent_year}/{num}/EU",
                f"{parent_year}/{num_raw}/EU",
            ])
    except Exception:
        parent_patterns = []

    regex_clauses: list[str] = []
    if esc_celex:
        regex_clauses.append(f'REGEX(?title, "{re.escape(esc_celex)}", "i")')
    for p in parent_patterns:
        regex_clauses.append(f'REGEX(?title, "{re.escape(p)}", "i")')
    for token in short_tokens:
        regex_clauses.append(f'REGEX(?title, "{re.escape(token)}", "i")')

    if not regex_clauses:
        regex_clauses = [
            'REGEX(?title, "implementing|delegated|supplementing", "i")'
        ]

    return " ||\n        ".join(regex_clauses)


def build_level2_query(parent_celex: str, parent_short: str, offset: int = 0) -> str:
    title_filter = build_level2_title_match_clauses(parent_celex, parent_short)
    return f"""
PREFIX cdm:  <http://publications.europa.eu/ontology/cdm#>
PREFIX lang: <http://publications.europa.eu/resource/authority/language/>
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>

SELECT DISTINCT ?celex ?title ?date ?relation
WHERE {{
    {{
        ?parent_work cdm:resource_legal_id_celex ?parent_celex_val .
        FILTER(str(?parent_celex_val) = "{parent_celex}")
        ?work ?relation ?parent_work .
        FILTER(?relation IN (
            cdm:resource_legal_amends_resource_legal,
            cdm:resource_legal_implements_resource_legal,
            cdm:resource_legal_extends_application_resource_legal,
            cdm:resource_legal_adds_to_resource_legal,
            cdm:resource_legal_completes_resource_legal,
            cdm:resource_legal_related_to_resource_legal,
            cdm:resource_legal_based_on_resource_legal
        ))
        ?work a cdm:legislation_secondary .
        ?work cdm:resource_legal_id_celex ?celex .
        ?expression cdm:expression_belongs_to_work ?work .
        ?expression cdm:expression_uses_language lang:ENG .
        ?expression cdm:expression_title ?title .
        OPTIONAL {{ ?work cdm:work_date_document ?date . }}
        FILTER regex(?title, "delegated regulation|implementing regulation|delegated directive|implementing directive|regulatory technical standard|implementing technical standard|RTS|ITS", "i")
    }}
    UNION
    {{
        ?work a cdm:legislation_secondary .
        ?work cdm:resource_legal_id_celex ?celex .
        ?expression cdm:expression_belongs_to_work ?work .
        ?expression cdm:expression_uses_language lang:ENG .
        ?expression cdm:expression_title ?title .
        OPTIONAL {{ ?work cdm:work_date_document ?date . }}
        FILTER regex(?title, "delegated regulation|implementing regulation|delegated directive|implementing directive|regulatory technical standard|implementing technical standard|RTS|ITS", "i")
        FILTER(
            {title_filter}
        )
        BIND("title-match" AS ?relation)
    }}
}}
ORDER BY DESC(?date)
LIMIT  {PAGE_SIZE}
OFFSET {offset}
"""


def title_mentions_parent(title: str, parent_celex: str) -> bool:
    t = title.lower()
    if not t or not parent_celex:
        return False
    if parent_celex.lower() in t:
        return True

    try:
        year = parent_celex[1:5]
        num_raw = parent_celex[6:]
        num = str(int(num_raw))
    except Exception:
        year = ""
        num = ""

    if year and num:
        if f"{year}/{num}" in t or f"{year}/{num_raw}" in t:
            return True
    return False


def fetch_level2_for_parent(parent_celex: str, parent_short: str) -> list[dict]:
    all_rows: list[dict] = []
    offset = 0
    debug_print(f"Start Level2 fetch for parent {parent_celex} ('{parent_short}')")
    while True:
        query = build_level2_query(parent_celex, parent_short, offset)
        debug_print(f"  Level2 query offset={offset} (parent={parent_celex})")
        resp = None
        # try a few attempts but keep them short to avoid long blocking
        for attempt in range(3):
            try:
                debug_print(f"    Attempt {attempt+1}/3 for parent {parent_celex}")
                resp = _sparql_request(query)
                break
            except Exception as e:
                debug_print(f"    Attempt {attempt+1} failed for {parent_celex}: {e}")
                if attempt < 2:
                    time.sleep(2)
        if resp is None:
            debug_print(f"    All attempts failed for parent {parent_celex}; aborting Level2 fetch for this parent.")
            return all_rows

        try:
            bindings = resp.json().get("results", {}).get("bindings", [])
        except Exception as e:
            debug_print(f"    Failed to parse SPARQL JSON for parent {parent_celex}: {e}\n{traceback.format_exc()}")
            return all_rows

        debug_print(f"    Received {len(bindings)} bindings (offset={offset}) for parent {parent_celex}")
        if not bindings:
            break
        for item in bindings:
            celex = item.get("celex", {}).get("value", "")
            title = item.get("title", {}).get("value", "")
            date = item.get("date", {}).get("value", "")
            relation = item.get("relation", {}).get("value", "")
            is_direct_link = relation.startswith("http://publications.europa.eu/ontology/cdm#resource_legal_")
            if not is_direct_link and not title_mentions_parent(title, parent_celex):
                continue
            all_rows.append({
                "celex": celex,
                "title": title,
                "date": date,
                "url": f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}",
            })
        if len(bindings) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    debug_print(f"Finished Level2 fetch for parent {parent_celex}: found {len(all_rows)} acts")
    return all_rows


def deduplicate_rows(rows: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
    for r in rows:
        key = (r.get("celex"), r.get("parent_celex"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# Phase 1 — SPARQL query (broad fetch of Level 1 acts)
# ---------------------------------------------------------------------------
#
# Level 1 = acts adopted by the European Parliament & Council jointly,
#           or by the Council acting alone.
#
# We identify Level 1 by a POSITIVE title regex:
#   - "Regulation (EU) ..."
#   - "Directive ..."  (not starting with "Commission")
#   - "Council Regulation ..."
#   - "Council Directive ..."
#
# And a NEGATIVE filter that excludes Commission-authored acts:
#   - "Commission Implementing Regulation ..."
#   - "Commission Delegated Regulation ..."
#   - "Commission Regulation ..."
#   - "Commission Directive ..."
#   - "Commission Delegated Directive ..."
#
# We deliberately skip EuroVoc and keyword filters in SPARQL to avoid the
# inconsistent-metadata trap.  Python-side filtering in Phase 2 is used
# instead.
#
# ---------------------------------------------------------------------------

def build_sparql_query(offset: int = 0) -> str:
    return f"""
PREFIX cdm:  <http://publications.europa.eu/ontology/cdm#>
PREFIX lang: <http://publications.europa.eu/resource/authority/language/>
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>

SELECT DISTINCT ?celex ?title ?date
WHERE {{

    ?work a cdm:legislation_secondary .
    ?work cdm:resource_legal_id_celex ?celex .

    # In-force acts only
    ?work cdm:resource_legal_in-force "true"^^xsd:boolean .

    # English expression title
    ?expression cdm:expression_belongs_to_work ?work .
    ?expression cdm:expression_uses_language lang:ENG .
    ?expression cdm:expression_title ?title .

    OPTIONAL {{ ?work cdm:work_date_document ?date . }}

    # CELEX type filter: Regulations (R) and Directives (L) only
    FILTER(
        REGEX(?celex, "^3[0-9]{{4}}R")
        || REGEX(?celex, "^3[0-9]{{4}}L")
    )

    # Level 1 positive filter: must look like an EP+Council or Council act
    FILTER(
        REGEX(?title,
            "^(Regulation \\\\(EU|Directive (\\\\(EU\\\\) )?[0-9]|Directive [0-9]|Council Regulation|Council Directive)",
            "i"
        )
    )

    # Level 1 negative filter: exclude Commission-authored acts
    FILTER(
        !REGEX(?title,
            "^Commission (Implementing |Delegated |Regulation|Directive)",
            "i"
        )
    )

}}
ORDER BY DESC(?date)
LIMIT  {PAGE_SIZE}
OFFSET {offset}
"""


# ---------------------------------------------------------------------------
# Fetch with paging
# ---------------------------------------------------------------------------

def _sparql_request(query: str) -> requests.Response:
    """
    Send a SPARQL query, trying POST first then GET as fallback.
    A descriptive User-Agent is set to avoid 403s from the CELLAR proxy.
    """
    headers = {
        "Accept":     "application/sparql-results+json",
        "User-Agent": "eu-financial-legislation-exporter/2.0 (research; contact: user@example.com)",
    }
    # Try POST (preferred by CELLAR for large queries)
    # Use a shorter timeout so a single blocked request doesn't stall Phase 4 for minutes.
    timeout_seconds = 60
    try:
        print(f"[DEBUG {_ts()}] SPARQL POST → endpoint={SPARQL_ENDPOINT} timeout={timeout_seconds}s", flush=True)
        resp = requests.post(
            SPARQL_ENDPOINT,
            data={"query": query},
            headers=headers,
            timeout=timeout_seconds,
        )
        if resp.status_code != 405:   # 405 = Method Not Allowed → fall through to GET
            resp.raise_for_status()
            print(f"[DEBUG {_ts()}] SPARQL POST succeeded (status={resp.status_code})", flush=True)
            return resp
    except Exception as e:
        print(f"[DEBUG {_ts()}] SPARQL POST error: {e}", flush=True)

    # Fallback: GET
    try:
        print(f"[DEBUG {_ts()}] SPARQL GET → endpoint={SPARQL_ENDPOINT} timeout={timeout_seconds}s", flush=True)
        resp = requests.get(
            SPARQL_ENDPOINT,
            params={"query": query},
            headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
            timeout=timeout_seconds,
        )
        resp.raise_for_status()
        print(f"[DEBUG {_ts()}] SPARQL GET succeeded (status={resp.status_code})", flush=True)
        return resp
    except Exception as e:
        print(f"[DEBUG {_ts()}] SPARQL GET error: {e}", flush=True)
        raise


def fetch_all_level1_acts() -> list[dict]:
    all_rows: list[dict] = []
    offset = 0

    while True:
        query = build_sparql_query(offset)
        print(f"  Querying SPARQL (offset={offset})…", flush=True)

        for attempt in range(3):
            try:
                resp = _sparql_request(query)
                break
            except requests.RequestException as exc:
                if attempt == 2:
                    raise
                print(f"    Retrying after error: {exc}")
                time.sleep(5 * (attempt + 1))

        bindings = resp.json().get("results", {}).get("bindings", [])
        if not bindings:
            break

        for item in bindings:
            celex = item.get("celex", {}).get("value", "")
            title = item.get("title", {}).get("value", "")
            date  = item.get("date",  {}).get("value", "")
            all_rows.append({
                "celex": celex,
                "title": title,
                "date":  date,
                "url":   f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}",
            })

        print(f"    → {len(bindings)} rows received (total so far: {len(all_rows)})")

        if len(bindings) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    return all_rows


# ---------------------------------------------------------------------------
# Merge seed list with query results
# ---------------------------------------------------------------------------

def fetch_celex_details(celex_ids: list[str]) -> list[dict]:
    """
    Fetch title + date for a list of CELEX IDs that were not returned by
    the broad SPARQL query (e.g. not in-force, or metadata gap).
    Falls back to the seed title if SPARQL returns nothing.
    """
    if not celex_ids:
        return []

    values_block = " ".join(f'"{c}"' for c in celex_ids)
    query = f"""
PREFIX cdm:  <http://publications.europa.eu/ontology/cdm#>
PREFIX lang: <http://publications.europa.eu/resource/authority/language/>

SELECT DISTINCT ?celex ?title ?date
WHERE {{
    ?work cdm:resource_legal_id_celex ?celex .
    FILTER(?celex IN ({', '.join(f'"{c}"' for c in celex_ids)}))

    OPTIONAL {{
        ?expression cdm:expression_belongs_to_work ?work .
        ?expression cdm:expression_uses_language lang:ENG .
        ?expression cdm:expression_title ?title .
    }}
    OPTIONAL {{ ?work cdm:work_date_document ?date . }}
}}
"""
    try:
        resp = _sparql_request(query)
        resp.raise_for_status()
        rows = []
        for item in resp.json().get("results", {}).get("bindings", []):
            celex = item.get("celex", {}).get("value", "")
            title = item.get("title", {}).get("value", "") or SEED_CELEX.get(celex, "")
            date  = item.get("date",  {}).get("value", "")
            if celex:
                rows.append({
                    "celex": celex,
                    "title": title,
                    "date":  date,
                    "url":   f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}",
                })
        return rows
    except Exception as exc:
        print(f"  Warning: seed fetch failed ({exc}); using seed titles only.")
        return [
            {
                "celex": c,
                "title": SEED_CELEX[c],
                "date":  "",
                "url":   f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{c}",
            }
            for c in celex_ids
        ]


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def deduplicate(rows: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for row in rows:
        if row["celex"] not in seen:
            seen.add(row["celex"])
            out.append(row)
    return out


# ---------------------------------------------------------------------------
# Classify acts
# ---------------------------------------------------------------------------

def classify(rows: list[dict]) -> list[dict]:
    """Return rows where the title matches financial-services criteria."""
    return [r for r in rows if is_financial_services(r["title"])]


# ---------------------------------------------------------------------------
# Detect act type from CELEX / title
# ---------------------------------------------------------------------------

def detect_type(celex: str, title: str) -> str:
    if "R" in celex[5:6]:
        return "Regulation"
    if "L" in celex[5:6]:
        return "Directive"
    t = title.lower()
    if "regulation" in t:
        return "Regulation"
    if "directive" in t:
        return "Directive"
    return "Unknown"


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_txt(rows: list[dict], file_path: str, heading: str) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(f"{heading}\n")
        f.write("=" * 80 + "\n")
        f.write(f"Generated : {datetime.utcnow().isoformat()} UTC\n")
        f.write(f"Total acts: {len(rows)}\n")
        f.write("=" * 80 + "\n\n")

        for idx, row in enumerate(rows, start=1):
            act_type = detect_type(row["celex"], row["title"])
            level = row.get("level", "Level 1")
            parent_fw = row.get("parent_framework", "")
            parent_celex = row.get("parent_celex", "")
            level2_type = row.get("level2_type", "")
            f.write(f"{idx:>3}. {row['title']}\n")
            f.write(f"       Level    : {level}\n")
            f.write(f"       Type     : {act_type}\n")
            if level == "Level 2":
                f.write(f"       Level2   : {level2_type}\n")
                f.write(f"       Parent   : {parent_fw} ({parent_celex})\n")
            f.write(f"       Category : {row.get('category', '')}\n")
            f.write(f"       CELEX    : {row['celex']}\n")
            f.write(f"       Date     : {row['date']}\n")
            f.write(f"       URL      : {row['url']}\n")
            f.write("\n")


def export_csv(rows: list[dict], file_path: str) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df = pd.DataFrame([
        {
            "celex":    r["celex"],
            "level":    r.get("level", "Level 1"),
            "type":     detect_type(r["celex"], r["title"]),
            "level2_type": r.get("level2_type", ""),
            "category": r.get("category", ""),
            "parent_framework": r.get("parent_framework", ""),
            "parent_celex": r.get("parent_celex", ""),
            "title":    r["title"],
            "date":     r["date"],
            "url":      r["url"],
        }
        for r in rows
    ])
    df.to_csv(file_path, index=False)


def export_level1_files(rows: list[dict]) -> None:
    export_txt(rows, LEVEL1_TXT_FILE, "EU FINANCIAL SERVICES — LEVEL 1 LEGISLATION")
    export_csv(rows, LEVEL1_CSV_FILE)


def export_level2_files(rows: list[dict]) -> None:
    export_txt(rows, LEVEL2_TXT_FILE, "EU FINANCIAL SERVICES — LEVEL 2 LEGISLATION")
    export_csv(rows, LEVEL2_CSV_FILE)


def export_combined_files(rows: list[dict]) -> None:
    export_txt(rows, COMBINED_TXT_FILE, "EU FINANCIAL SERVICES — LEVEL 1 + LEVEL 2 LEGISLATION")
    export_csv(rows, COMBINED_CSV_FILE)


def load_rows_from_csv(file_path: str, default_level: str | None = None) -> list[dict]:
    if not os.path.exists(file_path):
        return []
    try:
        df = pd.read_csv(file_path, dtype=str).fillna("")
        rows = df.to_dict(orient="records")
        if default_level is not None:
            for row in rows:
                if not row.get("level"):
                    row["level"] = default_level
        return rows
    except Exception as exc:
        print(f"Warning: failed to load CSV {file_path}: {exc}")
        return []


def gather_financial_legislation() -> list[dict]:
    # New workflow: fetch Level 1 quickly, return them; Level 2 fetched incrementally
    print("=" * 60)
    print("EU Financial Services Level 1 Legislation Exporter")
    print("=" * 60)

    print("\n[Phase 1] Fetching Level 1 acts from CELLAR (SPARQL)…")
    sparql_rows = fetch_all_level1_acts()
    print(f"  Total Level 1 acts fetched: {len(sparql_rows)}")

    print("\n[Phase 2] Classifying as financial-services acts…")
    classified = classify(sparql_rows)
    print(f"  Acts matching financial-services criteria: {len(classified)}")

    print("\n[Phase 3] Merging hardcoded seed list…")
    present_celex = {r["celex"] for r in classified}
    missing = [c for c in SEED_CELEX if c not in present_celex]

    if missing:
        print(f"  Seed acts NOT found by SPARQL ({len(missing)}): {', '.join(missing)}")
        seed_rows = fetch_celex_details(missing)
        classified.extend(seed_rows)
        print(f"  Added {len(seed_rows)} acts from seed list.")
    else:
        print("  All seed acts already present in SPARQL results. ✓")

    classified = deduplicate(classified)
    assign_category(classified)

    # Mark Level 1 items
    for r in classified:
        r["level"] = "Level 1"

    # Build Level 1 framework registry (do not fetch Level 2 here)
    frameworks = build_level1_frameworks(classified)

    # Export Level 1 results immediately so the user sees data
    classified.sort(key=lambda r: r.get("date", "") or "", reverse=True)
    print("\n[Export] Writing Level 1 output files…")
    export_level1_files(classified)
    print(f"  TXT → {LEVEL1_TXT_FILE}")
    print(f"  CSV → {LEVEL1_CSV_FILE}")

    # Return Level 1 rows and frameworks for incremental Level 2 fetching
    return classified, frameworks


def clear_tree(tree: ttk.Treeview) -> None:
    for item in tree.get_children():
        tree.delete(item)


def populate_tree(tree: ttk.Treeview, rows: list[dict]) -> None:
    clear_tree(tree)
    for row in rows:
        category = row.get("category", "")
        level = row.get("level", "Level 1")
        tag = category if level == "Level 1" else f"{category}|Level 2"
        tree.insert("", "end", values=(
            row["celex"],
            level,
            detect_type(row["celex"], row["title"]),
            row.get("level2_type", ""),
            category,
            row.get("parent_framework", ""),
            row["title"],
            row["date"],
            row["url"],
        ), tags=(tag,))


def create_gui() -> None:
    root = tk.Tk()
    root.title("EU Financial Services Level 1 & Level 2 Legislation Exporter")
    root.geometry("1200x600")

    header = ttk.Label(root, text="EU Financial Services Level 1 & Level 2 Legislation Exporter", font=(None, 16, "bold"))
    header.pack(padx=10, pady=(10, 5), anchor="w")

    button_frame = ttk.Frame(root)
    button_frame.pack(fill="x", padx=10)

    fetch_level1_button = ttk.Button(button_frame, text="Fetch Level 1 acts")
    fetch_level1_button.pack(side="left")
    fetch_level2_button = ttk.Button(button_frame, text="Fetch Level 2 acts")
    fetch_level2_button.pack(side="left", padx=(6, 0))

    category_var = tk.StringVar(value="All Categories")
    category_label = ttk.Label(button_frame, text="Category:")
    category_label.pack(side="left", padx=(10, 4))

    categories = ["All Categories"] + CATEGORIES
    category_selector = ttk.Combobox(
        button_frame,
        textvariable=category_var,
        values=categories,
        state="readonly",
        width=32,
    )
    category_selector.pack(side="left")

    level_var = tk.StringVar(value="All Levels")
    level_label = ttk.Label(button_frame, text="Level:")
    level_label.pack(side="left", padx=(10, 4))
    level_selector = ttk.Combobox(
        button_frame,
        textvariable=level_var,
        values=["All Levels", "Level 1", "Level 2"],
        state="readonly",
        width=12,
    )
    level_selector.pack(side="left")

    status_label = ttk.Label(button_frame, text="Loading existing output files if available. Double-click URL cells to open links.")
    status_label.pack(side="left", padx=15)

    # Progress bar and label for Level 2 discovery
    progress_bar = ttk.Progressbar(button_frame, orient="horizontal", length=200, mode="determinate")
    progress_bar.pack(side="left", padx=(12, 6))
    progress_label = ttk.Label(button_frame, text="")
    progress_label.pack(side="left")

    tree_frame = ttk.Frame(root)
    tree_frame.pack(fill="both", expand=True, padx=10, pady=10)

    columns = ("celex", "level", "type", "level2_type", "category", "parent_framework", "title", "date", "url")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
    for col in columns:
        tree.heading(col, text=col.upper())
        # sensible default widths
        tree.column(col, anchor="w", width=160)
    tree.column("celex", width=120)
    tree.column("level", width=90)
    tree.column("type", width=140)
    tree.column("level2_type", width=120)
    tree.column("category", width=240)
    tree.column("parent_framework", width=220)
    tree.column("title", width=420)
    tree.column("date", width=100)
    tree.column("url", width=320)

    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    tree.configure(yscroll=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True)

    loaded_rows: list[dict] = []
    level1_rows: list[dict] = []
    level2_rows: list[dict] = []
    level1_frameworks: dict[str, dict] = {}

    def append_rows(new_rows: list[dict]) -> None:
        nonlocal loaded_rows
        if not new_rows:
            return
        loaded_rows.extend(new_rows)
        apply_filter()

    def set_status(message: str, error: bool = False) -> None:
        status_label.config(text=message, foreground="red" if error else "black")

    def apply_filter() -> None:
        filtered = filter_by_category(loaded_rows, category_var.get())
        lvl = level_var.get()
        if lvl != "All Levels":
            filtered = [r for r in filtered if r.get("level") == lvl]
        populate_tree(tree, filtered)

    def refresh_buttons() -> None:
        fetch_level1_button.config(state="normal")
        fetch_level2_button.config(state="normal" if level1_frameworks else "disabled")

    def on_export_error(exc: Exception) -> None:
        set_status("Fetch failed. See console for details.", error=True)
        messagebox.showerror("Export Error", str(exc))
        refresh_buttons()

    def on_level1_fetch_complete(rows: list[dict], frameworks: dict[str, dict]) -> None:
        nonlocal loaded_rows, level1_rows, level1_frameworks
        level1_rows = deduplicate_rows(rows)
        level1_frameworks = frameworks
        loaded_rows = list(level1_rows)
        apply_filter()
        set_status(f"Level 1 fetch complete: {len(level1_rows)} acts exported to {LEVEL1_TXT_FILE}")
        refresh_buttons()

    def on_level2_fetch_complete(rows: list[dict]) -> None:
        nonlocal loaded_rows, level2_rows
        level2_rows = deduplicate_rows(rows)
        loaded_rows = deduplicate_rows(level1_rows + level2_rows)
        apply_filter()
        set_status(f"Level 2 fetch complete: {len(level2_rows)} acts exported to {LEVEL2_TXT_FILE}")
        refresh_buttons()

    def on_category_change(event: tk.Event | None = None) -> None:
        apply_filter()

    def on_level_change(event: tk.Event | None = None) -> None:
        apply_filter()

    def on_open_url(event: tk.Event) -> None:
        region = tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        column_id = tree.identify_column(event.x)
        if column_id != f"#{columns.index('url') + 1}":
            return
        item_id = tree.identify_row(event.y)
        if not item_id:
            return
        url = tree.set(item_id, "url")
        if url:
            webbrowser.open(url)

    def on_motion(event: tk.Event) -> None:
        region = tree.identify_region(event.x, event.y)
        column_id = tree.identify_column(event.x)
        if region == "cell" and column_id == f"#{columns.index('url') + 1}":
            tree.configure(cursor="hand2")
        else:
            tree.configure(cursor="")

    category_selector.bind("<<ComboboxSelected>>", on_category_change)
    level_selector.bind("<<ComboboxSelected>>", on_level_change)
    tree.bind("<Double-1>", on_open_url)
    tree.bind("<Motion>", on_motion)

    def load_existing_outputs() -> None:
        nonlocal loaded_rows, level1_rows, level2_rows, level1_frameworks
        existing_l1 = load_rows_from_csv(LEVEL1_CSV_FILE, default_level="Level 1")
        existing_l2 = load_rows_from_csv(LEVEL2_CSV_FILE, default_level="Level 2")
        if existing_l1 or existing_l2:
            level1_rows = deduplicate_rows(existing_l1)
            level2_rows = deduplicate_rows(existing_l2)
            level1_frameworks = build_level1_frameworks(level1_rows) if level1_rows else {}
            loaded_rows = deduplicate_rows(level1_rows + level2_rows)
            apply_filter()
            if level1_rows and level2_rows:
                set_status(f"Loaded existing Level 1 ({len(level1_rows)}) and Level 2 ({len(level2_rows)}) acts.")
            elif level1_rows:
                set_status(f"Loaded existing Level 1 acts ({len(level1_rows)}).")
            elif level2_rows:
                set_status(f"Loaded existing Level 2 acts ({len(level2_rows)}).")
            return
        set_status("No existing output files found. Click a fetch button to start.")

    def run_fetch_level1() -> None:
        fetch_level1_button.config(state="disabled")
        fetch_level2_button.config(state="disabled")
        set_status("Fetching Level 1 regulations from CELLAR…")

        def worker() -> None:
            try:
                rows, frameworks = gather_financial_legislation()
                export_level1_files(rows)
                export_combined_files(rows)
                print(f"[Export] Level 1 TXT → {LEVEL1_TXT_FILE}")
                print(f"[Export] Level 1 CSV → {LEVEL1_CSV_FILE}")
                root.after(0, lambda: on_level1_fetch_complete(rows, frameworks))
            except Exception as exc:
                print(f"Error during Level 1 fetch: {exc}")
                root.after(0, lambda: on_export_error(exc))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def run_fetch_level2() -> None:
        if not level1_frameworks:
            set_status("Please fetch or load Level 1 acts before fetching Level 2.", error=True)
            return
        fetch_level1_button.config(state="disabled")
        fetch_level2_button.config(state="disabled")
        set_status("Fetching Level 2 regulations from CELLAR…")
        progress_bar.configure(value=0)

        def worker() -> None:
            try:
                rows: list[dict] = []
                total = len(level1_frameworks)
                idx = 0
                print(f"\n[Phase 4] Discovering Level 2 acts for {total} frameworks...")
                for parent_celex, info in level1_frameworks.items():
                    idx += 1
                    parent_short = info.get("short_name", "")
                    debug_print(f"[Phase4] Processing framework {idx}/{total}: {parent_celex} ('{parent_short}')")
                    try:
                        found = fetch_level2_for_parent(parent_celex, parent_short)
                    except Exception as exc:
                        print(f"  Warning: Level2 fetch failed for {parent_celex}: {exc}")
                        found = []
                    chunk: list[dict] = []
                    for fr in found:
                        if fr.get("celex") == parent_celex:
                            continue
                        fr["level"] = "Level 2"
                        fr["parent_framework"] = info.get("short_name")
                        fr["parent_celex"] = parent_celex
                        fr["level2_type"] = detect_level2_type(fr.get("title", ""))
                        fr["category"] = info.get("category", "")
                        rows.append(fr)
                        chunk.append(fr)
                    if chunk:
                        root.after(0, lambda ch=chunk: append_rows(ch))
                    root.after(0, lambda i=idx, t=total: (progress_bar.configure(maximum=t), progress_bar.configure(value=i), progress_label.config(text=f"{i}/{t} frameworks")))
                    print(f"  [{idx}/{total}] {parent_celex} → {len(chunk)} Level2 acts")

                rows = deduplicate_rows(rows)
                if rows:
                    export_level2_files(rows)
                merged = deduplicate_rows(level1_rows + rows)
                export_combined_files(merged)
                print(f"[Export] Level 2 TXT → {LEVEL2_TXT_FILE}")
                print(f"[Export] Level 2 CSV → {LEVEL2_CSV_FILE}")
                root.after(0, lambda: on_level2_fetch_complete(rows))
            except Exception as exc:
                print(f"Error during Level 2 fetch: {exc}")
                root.after(0, lambda: on_export_error(exc))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def adjust_hex_color(hex_color: str, factor: float = 0.96) -> str:
        # Darken/lighten a hex color by factor (0-1 darken, >1 lighten)
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        r = max(0, min(255, int(r * factor)))
        g = max(0, min(255, int(g * factor)))
        b = max(0, min(255, int(b * factor)))
        return f"#{r:02x}{g:02x}{b:02x}"

    for category, color in CATEGORY_COLORS.items():
        tree.tag_configure(category, background=color)
        # Slightly adjust color for Level 2 rows to differentiate
        level2_tag = f"{category}|Level 2"
        tree.tag_configure(level2_tag, background=adjust_hex_color(color, 0.97))

    fetch_level1_button.config(command=run_fetch_level1)
    fetch_level2_button.config(command=run_fetch_level2)
    fetch_level2_button.config(state="disabled")
    load_existing_outputs()
    refresh_buttons()

    root.mainloop()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    create_gui()


if __name__ == "__main__":
    main()