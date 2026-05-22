# EU Financial Services Legislation Exporter

A Python-based exporter designed to collect, classify and export **Level 1** and **Level 2** EU financial services legislation from **EUR-Lex**.

This project was developed as an experimental legal-tech prototype using AI-assisted (“vibe coded”) development techniques. The objective was to explore how legal and regulatory expertise can be translated into executable code to automate legislative mapping exercises.

The tool is designed for:

* lawyers,
* compliance professionals,
* regulatory teams,
* policy analysts,
* RegTech developers,
* and legal operations professionals.

---

# Overview

The exporter retrieves EU legislation related to financial services and classifies it into structured regulatory categories.

The script:

* fetches Level 1 EU legislative acts,
* identifies associated Level 2 measures,
* classifies legislation into regulatory domains,
* and exports the results into structured datasets.

The resulting outputs can support:

* regulatory inventories,
* compliance mapping,
* legal research,
* obligation mapping,
* horizon scanning,
* and internal regulatory intelligence workflows.

---

# Features

## Level 1 Legislation Collection

Collects major EU financial services frameworks, including:

* Regulations
* Directives
* Amending acts
* Omnibus packages

---

## Level 2 Legislation Collection

Fetches associated:

* Delegated Regulations
* Implementing Regulations
* RTS
* ITS
* Delegated Directives
* Technical standards

---

## Classification Engine

Automatically classifies legislation into categories such as:

* Banking & Prudential
* Payments
* AML/CFT
* Capital Markets & MiFID
* Asset Management & Funds
* ESG & Sustainable Finance
* Insurance & Pensions
* Crypto Assets
* Operational Resilience & ICT
* Financial Reporting & Audit

---

## Structured Export

Exports results into machine-readable formats for downstream processing.

Typical outputs include:

* CSV
* TXT

(depending on configuration)

---

# Example Use Cases

This tool can assist with:

## Regulatory Mapping

Identify legislation relevant to:

* banking,
* payments,
* AML/CFT,
* crypto-assets,
* ESG,
* operational resilience,
* or other regulatory domains.

---

## Compliance Inventories

Build internal inventories of:

* applicable legislation,
* Level 2 technical standards,
* implementing acts,
* delegated acts.

---

## Horizon Scanning

Track:

* newly adopted legislation,
* amending packages,
* delegated regulations,
* and evolving EU regulatory frameworks.

---

## Legal Research Automation

Reduce manual legislative identification work across large EU regulatory datasets.

---

# Tech Stack

* Python
* EUR-Lex APIs / feeds
* Requests
* XML / HTML parsing
* Data classification logic
* Structured export utilities

---

# Installation

## Clone the repository

```bash
git clone https://github.com/Filippakis/EU-financial-services-legislation-fetcher.git
cd EU-financial-services-legislation-fetcher
```

---

## Create a virtual environment

```bash
python -m venv venv
```

Activate the environment:

### macOS / Linux

```bash
source venv/bin/activate
```

### Windows

```bash
venv\Scripts\activate
```

---

## Install dependencies

```bash
pip install -r requirements.txt
```

---

# Usage

Run the exporter:

```bash
python exporter.py
```

The script will:

1. fetch Level 1 legislation,
2. identify related Level 2 measures,
3. classify legislation,
4. and export structured outputs.

---

# Project Structure

```bash
.
├── exporter.py
├── requirements.txt
├── output/
│   ├── level1.csv
│   ├── level2.csv
│   └── classifications.json
└── README.md
```

---

# Current Limitations

This project is an early-stage prototype with certain limitations.

The current filtering and classification engine relies heavily on:

* keyword matching,
* heuristics,
* and manually curated seed lists.

As a result:

* some non-financial legislation may be incorrectly included,
* while some relevant legislation may be missed.

Examples observed during testing:

* agricultural legislation incorrectly captured,
* certain niche financial-services frameworks omitted.

This is expected in a lightweight prototype and highlights the importance of:

* iterative refinement,
* legal subject matter expertise,
* and engineering-driven testing.

---

# Future Improvements

Potential enhancements include:

* improved NLP-based classification,
* semantic similarity matching,
* EUR-Lex taxonomy integration,
* EuroVoc integration,
* smarter Level 2 relationship detection,
* better exclusion logic,
* confidence scoring,
* incremental updates,
* API interface,
* and web dashboard integration.

---

# Why This Project Exists

This project was built as an experiment in AI-assisted legal engineering.

The core idea is simple:

> legal and regulatory expertise can increasingly be translated directly into executable code.

Large language models make it possible for legal and compliance professionals to rapidly prototype highly customized internal tools using natural-language instructions.

This exporter was developed in approximately two hours using iterative AI-assisted development techniques.

It is not intended to replace production-grade regulatory intelligence systems. Instead, it demonstrates how:

* legal expertise,
* engineering literacy,
* and AI tooling

can combine to significantly accelerate legal-tech development.

---

# Disclaimer

This tool is provided for research and informational purposes only.

It does not constitute:

* legal advice,
* regulatory advice,
* or a comprehensive statement of applicable law.

This tool is not to relied upon for any legal or regulatory task. Users should independently validate all outputs before using them for legal or compliance purposes.

---

# License

MIT License

---

# Contributions

Contributions, suggestions and improvements are welcome.

Potential areas for contribution include:

* classification logic,
* NLP enhancements,
* testing,
* export formats,
* and performance optimization.

---

# Author

Developed by George (Giorgos) Filippakis, a legal and regulatory professional with a CS background, exploring AI-assisted legal engineering and compliance automation.
