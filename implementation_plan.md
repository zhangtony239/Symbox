# Implementation Plan - Symbox Development

Symbox is a syntax-driven symbolic reasoning sandbox using natural language syntactic categories (Subject, Verb, Adj, Tags) for knowledge representation, Python OOP as implementation carrier, and `ltms` truth maintenance for reasoning.

This plan details the full implementation of Symbox, its CLI delivered via `uv tool`, git-backed Snapper version control, embedding similarity threshold checking, Worry/Attention meta objects, and stress/load testing with `pytest`.

## User Review Required

> [!IMPORTANT]
> - **CLI Invocation**: The CLI entrypoint `sbox` will support both standard CLI subcommands (`sbox create foo`, `sbox set foo ...`) and slash-prefixed syntax (`/sbox create foo`, `sbox /sbox create foo`) for LLM agent convenience.
> - **Dependency Management**: Dependencies (`ltms`, `z3-solver`, `click`, `httpx`, `python-dotenv`, `pytest`) will be managed via `uv`. CLI will be testable via `uv tool install .` and `uv run sbox`.
> - **Performance Benchmarks**: Load and stress tests will be located in `tests/test_performance.py` and run via `uv run pytest`.

## Proposed Changes

### Configuration & Package Dependencies

#### [MODIFY] [pyproject.toml](file:///c:/repos/Symbox/pyproject.toml)
- Add dependencies (`click`, `httpx`, `python-dotenv`, `pytest`, `pydantic`).
- Register `sbox` script entry point (`symbox.cli:main`).

---

### Core Data Models & Syntax Categories

#### [NEW] [symbox/core/subject.py](file:///c:/repos/Symbox/symbox/core/subject.py)
- `Subject` class representing Subject (S) / Object (O).
- Has `name`, `kind` (`physical`, `abstract`, `meta`), `attributes` (dict with observer property setter hooks), `adj` (dict of `Adj` objects), and `tags` (set).
- Dynamic tag derivation when setting `adj` with `implies_tags`.

#### [NEW] [symbox/core/adj.py](file:///c:/repos/Symbox/symbox/core/adj.py)
- `Adj` class representing adjective/attribute patch bag.
- Tracks `value`, `since`, `justification`, and `implies_tags`.

#### [NEW] [symbox/core/verb.py](file:///c:/repos/Symbox/symbox/core/verb.py)
- `Verb` class representing predicates (V).
- Support `kind` constraints on `domain` and `range`.
- Supports rules (`check(s, o) -> bool`), veto (intercept) rules, and modify rules.

#### [NEW] [symbox/core/meta.py](file:///c:/repos/Symbox/symbox/core/meta.py)
- `Worry`: Meta-subject watching value conditions on subjects (value-domain to symbol-domain bridge).
- `Attention`: Meta-cognitive context focus subject.

---

### LTMS Reasoning Engine & Threshold Detection

#### [NEW] [symbox/core/ltms_wrapper.py](file:///c:/repos/Symbox/symbox/core/ltms_wrapper.py)
- Integrates PyPI `ltms.LTMS` engine.
- Maps Subjects, Verbs, SVO facts, Adj states, and Worry conditions into LTMS nodes (`TmsNode`).
- Manages clause registration, truth propagation, contradiction detection, and belief revision (`--if-force`).

#### [NEW] [symbox/core/embedding.py](file:///c:/repos/Symbox/symbox/core/embedding.py)
- `EmbeddingDetector` for Adj key similarity checks.
- Reads `.env` for `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_MODEL`, `SIMILARITY_THRESHOLD`.
- Computes cosine similarity of embeddings (via HTTP endpoint or fallback text similarity).
- Triggers `confirm_needed` response if similarity > threshold and `--force` is missing.

#### [NEW] [symbox/core/backup.py](file:///c:/repos/Symbox/symbox/core/backup.py)
- `BackupManager` for snapper-style git version control.
- Manages git bare repository at `./.sbox/backups/`.
- Implements `create`, `delete`, `rollback`, and `log`.

#### [NEW] [symbox/core/storage.py](file:///c:/repos/Symbox/symbox/core/storage.py)
- JSON state storage under `./.sbox/state.json` to persist graph, subjects, verbs, adj, and logic rules across CLI invocations.

#### [NEW] [symbox/core/engine.py](file:///c:/repos/Symbox/symbox/core/engine.py)
- `SymboxEngine`: Main coordinator tying together state storage, LTMS wrapper, embedding detector, worry observers, and backup manager.
- Atomic transaction execution (commit on success, rollback on contradiction/error).

#### [NEW] [symbox/core/dynamic_bind.py](file:///c:/repos/Symbox/symbox/core/dynamic_bind.py)
- Dynamically loads Python source files (`-f src.py`) to bind custom `check(s, o)` functions or `Worry` classes to objects/verbs.

---

### CLI Interface & UV Delivery

#### [NEW] [symbox/cli.py](file:///c:/repos/Symbox/symbox/cli.py)
- `sbox` command line tool using `click`.
- Command handlers:
  - `create [obj_name] [--kind physical|abstract|meta]`
  - `delete [obj_name]`
  - `bind [obj_name] [func_name] -f src.py [--verb]`
  - `unbind [obj_name] [func_name] [--verb]`
  - `set [obj_name] [kv_dict_or_str] [--force]`
  - `unset [obj_name] [keys...]`
  - `svo [S] [V] [O] [--if-force]` and fallback positional `sbox [S] [V] [O] [--if-force]`
  - `list [objects|verbs|backups|obj_name]`
  - `backup [create|delete|rollback|log]`
- Standardized JSON and formatted text output, non-zero exit code on unhandled contradictions.

#### [NEW] [symbox/__init__.py](file:///c:/repos/Symbox/symbox/__init__.py)
- Expose main version and core classes.

---

### Verification & Performance Testing Suite

#### [NEW] [tests/test_unit.py](file:///c:/repos/Symbox/tests/test_unit.py)
- Tests for core domain models (Subject, Verb, Adj, Worry, Attention).
- LTMS integration tests and truth propagation logic.

#### [NEW] [tests/test_cli.py](file:///c:/repos/Symbox/tests/test_cli.py)
- Integration tests executing `sbox` CLI subcommands end-to-end.
- Tests embedding similarity confirmation flow and git backup snapper commands.

#### [NEW] [tests/test_performance.py](file:///c:/repos/Symbox/tests/test_performance.py)
- Stress and performance benchmarks using `pytest`:
  - 1,000+ Subjects & 10,000+ SVO assertions propagation speed.
  - High-frequency Worry value observation and symbol compilation.
  - Backup creation/rollback benchmark.

## Verification Plan

### Automated Tests
- Run full test suite with `uv run pytest`
- Run stress test suite with `uv run pytest tests/test_performance.py -v`
- Install CLI via `uv tool install . --force` and test `sbox --help` / `sbox create` / `sbox list`

### Manual Verification
- Test CLI commands with slash syntax: `sbox /sbox create test_obj`
- Test embedding similarity threshold confirmation and `--force` override.
- Test git backup log and rollback behavior in `./.sbox/backups/`.
