# Contributing to LLM Daily

Thanks for helping. Small, focused pull requests are easiest to review.

## Setup

```bash
uv sync --extra dev --extra openai --extra x
uv run pytest -q
uv run ruff check .
```

Optional: install the pre-commit hooks (gitleaks secret scan + ruff).

```bash
uvx pre-commit install
```

## Ground rules

- **Never commit secrets.** Keys live in `.env` locally and in GitHub Actions secrets in CI.
- **Never commit third-party content.** Do not add copies of other newsletters, raw tweets, or
  full Reddit post bodies. Store links, titles and your own summaries only.
- Tests must not call the network. Use the fake clients in `tests/` as examples.

## Adding a data source

1. Create `llm_daily/collectors/<name>_collector.py` that subclasses `BaseCollector` and
   implements `collect_data()` and `format_for_llm()`.
2. Put any source lists in `config/sources.yaml`, not in code.
3. Wire it into `llm_daily/cli.py` behind a `--skip-<name>` flag.

## Adding an LLM provider

Most hosts work through the `openai` provider with `OPENAI_BASE_URL`. If a host needs its own SDK,
add a class in `llm_daily/llm/` that implements `complete(system, user, max_tokens) -> Completion`
and register it in `llm_daily/llm/factory.py`.
