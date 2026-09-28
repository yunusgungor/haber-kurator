# Project Memory -- haber-kurator

## Architecture
- HaberKuratorCore(WriterMixin, ScannerMixin, FetcherMixin, StateMachineMixin)
- Modules in haber_kurator/modules/: models.py, fetcher.py, scanner.py, writer.py, state_machine.py, llm.py
- haber_kurator_core.py: ~170 lines, pure inheritance aggregation
- writer_agent.py: backward-compat wrapper (delegates to core)
- modules/llm.py: shared LLM calling (async/sync/fallback)

## Key Consolidations
- WriterAgent (562 lines) -> WriterMixin (435 lines) + wrapper (73 lines)
- 7 duplicated async_call_llm patterns consolidated into modules/llm.py

## Completed Experiments
- E-023: LLM call consolidation (call_llm_with_fallback, call_llm_sync)
- E-022: WriterMixin extraction (WriterAgent -> WriterMixin)
- E-017: Embedding clustering (sentence-transformers all-MiniLM-L6-v2, threshold 0.18)
- E-014: Core refactor (4169->170 lines, 3 mixins)
- E-019: State machine 8->5 simplification
- E-020: Exception hierarchy cleanup

## Known Issues
- No pyproject.toml/requirements.txt -- deps via uv pip install only
- No unit tests for individual modules (only integration via core)
- Scikit-learn DeprecationWarning (jaccard_score preserve_binary) not yet suppressed
