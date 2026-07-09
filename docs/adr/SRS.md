# SRS — Agentic Document Intelligence Platform

## 1. Purpose
Async platform that ingests enterprise documents, extracts structured data via
local LLMs, validates it against configurable business rules, routes low-confidence
results through an AI review agent, and exports to configurable formats.

## 2. Scope (v1)
- Document type: Invoice (plugin-based; architecture supports N types)
- Input: REST upload (multipart). Email/cloud ingestion: out of scope v1.
- LLM: Ollama (qwen2.5:7b). Provider abstraction supports cloud LLMs.
- OCR: PyMuPDF (digital), Tesseract (scanned).

## 3. Non-functional requirements
- NFR-1: Upload endpoint responds < 500ms (processing is async).
- NFR-2: Every pipeline stage emits structured logs with a correlation/request ID.
- NFR-3: New document type requires zero changes to engine code.
- NFR-4: New validation rule requires zero changes to existing rules.
- NFR-5: All LLM calls are mockable in tests (no network in unit tests).

## 4. Functional requirements
- FR-1 (Ingestion): ...
- FR-2 (Understanding): ...
- FR-3 (Validation): ...        ← you write these
- FR-4 (Review): ...            ← you write these
- FR-5 (Output): ...            ← you write these

## 5. Pipeline states
UPLOADED → PROCESSING → EXTRACTED → VALIDATED → (REVIEW) → COMPLETED | FAILED | ESCALATED