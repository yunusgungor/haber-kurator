# Project Memory -- haber-kurator

## Architecture
- HaberKuratorCore(WriterMixin, ScannerMixin, FetcherMixin, StateMachineMixin)
- Modules in haber_kurator/modules/: models.py, fetcher.py, scanner.py, writer.py, state_machine.py
- haber_kurator_core.py: ~170 lines, pure inheritance aggregation
- writer_agent.py: backward-compat wrapper (delegates to core)

## Completed Experiments
- E-017: Embedding clustering (sentence-transformers all-MiniLM-L6-v2, threshold 0.18)
- E-014: Core refactor (4169->170 lines, 3 mixins)
- E-019: State machine 8->5 simplification
- E-020: Exception hierarchy cleanup

## Known Issues
- No pyproject.toml/requirements.txt -- deps via uv pip install only
- ScannerMixin and WriterMixin both have separate LLM calling (async vs sync)
- No unit tests for individual modules (only integration via core)
