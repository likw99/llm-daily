# LLM Daily

An open-source agent that collects the day's AI news and writes a newsletter with your own LLM key.
It has written the *LLM Daily* newsletter nearly every morning since March 2025.

It reads Reddit, arXiv, GitHub trending, Hugging Face, Product Hunt, TechCrunch,
VentureBeat and Sequoia, then writes four sections (Business, Products, Technology,
Research) plus Highlights, in English, Chinese or both. Each issue goes to a dated archive, a
static website with RSS, and optionally email (Kit or Buttondown), Telegram, Discord, Slack or Feishu.

## Try it without any keys

```bash
git clone https://github.com/likw99/llm-daily.git
cd llm-daily
uv sync
uv run llm-daily --dry-run --lang both
```

The dry run uses example data and an offline stub model. Open
`data/dry-run/site/index.html` to see the web archive it builds.

## Quickstart with your own key

```bash
git clone https://github.com/likw99/llm-daily.git
cd llm-daily
uv sync                 # add --extra openai for non-Anthropic providers
cp .env.example .env    # add one LLM key and your Reddit app credentials
uv run llm-daily --no-publish
```

The newsletter is written to `data/output/llm_newsletter_<date>.md` and to `archive/YYYY/MM/`.
Raw collector output for the day is saved under `data/output/`.

Useful flags: `--lang en|zh|both`, `--publishers`, `--no-publish`, `--dry-run`, `--provider`,
`--model`, `--skip-<source>` for each source, `--debug`. Run `uv run llm-daily --help` for all of them.

## How it stays honest

An automated newsletter is only useful if you can trust it, so the pipeline enforces a few rules:

- **No data, no section.** If a section's sources returned nothing, the section is left out. The
  model is never asked to fill a gap from its own knowledge.
- **Every item links to its source.** Prompts require one linked, dated bullet per item taken from
  the collected data. A validator then removes any bullet or paragraph without a link.
- **Failures are shown, not hidden.** Each issue ends with a "Sources & method" note listing the
  sources used, sources that were unavailable, sections left out, lines removed, the model and
  the tokens spent. The same facts are saved as JSON next to the issue in `archive/`.
- **Nothing to say, nothing sent.** If no section has content, no issue is published.

## Bring your own key

Only one LLM key is needed. Pick a provider with `LLMDAILY_PROVIDER` or `--provider`.

| Provider | Settings | Notes |
|---|---|---|
| Anthropic (default) | `ANTHROPIC_API_KEY`; optional `LLMDAILY_MODEL` (default `claude-sonnet-5-5`), `LLMDAILY_EFFORT` (default `medium`) | Uses the official SDK with retries and server-side refusal fallbacks. Set `LLMDAILY_FALLBACKS=off` to disable them. |
| OpenRouter | `LLMDAILY_PROVIDER=openai`, `OPENAI_BASE_URL=https://openrouter.ai/api/v1`, `OPENAI_API_KEY`, `LLMDAILY_MODEL` | Any model OpenRouter lists. |
| DeepSeek | `OPENAI_BASE_URL=https://api.deepseek.com`, `LLMDAILY_MODEL=deepseek-chat` | |
| Qwen (DashScope) | `OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`, `LLMDAILY_MODEL=qwen-plus` | |
| Ollama (local) | `OPENAI_BASE_URL=http://localhost:11434/v1`, `OPENAI_API_KEY=ollama`, `LLMDAILY_MODEL=llama3.1` | Free, runs on your machine. |
| OpenAI | `OPENAI_API_KEY`, `LLMDAILY_MODEL` | Leave `OPENAI_BASE_URL` unset. |

The `openai` provider needs the extra: `uv sync --extra openai`. If only `OPENAI_API_KEY` is set,
it is selected automatically.

The run log ends with the number of LLM calls and tokens used, so you can see what a day costs.

## Chinese edition

`--lang both` (or `LLMDAILY_LANG=both`) writes a Simplified Chinese edition next to the English one
with one extra LLM call. Links, names and dates are kept as they are, and a link-count check flags a
broken translation. `--lang zh` sends the Chinese edition instead of the English one.

## Where issues go

Choose publishers with `LLMDAILY_PUBLISHERS` (comma separated) or `--publishers`. The default is
`archive`. `--no-publish` keeps only the archive.

| Publisher | Settings | What it does |
|---|---|---|
| `archive` | none | Writes `archive/YYYY/MM/<date>.md`, the Chinese edition and a JSON record of the run. `llm-daily-site` turns the archive into a website with Atom feeds. |
| `kit` | `KIT_API_KEY`; `KIT_STATUS=draft` (default) or `send`; optional `KIT_SEGMENT_ID`, `KIT_TEMPLATE_ID`, `KIT_PUBLIC` | Creates a [Kit](https://kit.com) broadcast. Kit's free plan covers up to 10,000 subscribers. |
| `buttondown` | `BUTTONDOWN_API_KEY`; `NEWSLETTER_STATUS=draft` (default) or `about_to_send` | Creates a Buttondown email. |
| `telegram` | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Posts the Highlights and a link to a channel. |
| `webhook` | `LLMDAILY_WEBHOOK_URL`; optional `LLMDAILY_WEBHOOK_FORMAT` | Posts the Highlights and a link to Discord, Slack, Feishu/Lark (detected from the URL) or any JSON endpoint. |

Set `LLMDAILY_SITE_URL` to the site's public address so emails and posts can link to each issue.

## Data sources

- **Reddit** needs a free "script" app from [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps).
  Put its ID and secret in `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET`. The redirect URI can be
  `http://localhost:8000`; it is never used.
- **Subreddits and the X list** are configured in [`config/sources.yaml`](config/sources.yaml).
  Point `LLMDAILY_SOURCES` at another file to use your own.
- **GitHub, Hugging Face, Product Hunt** work without keys. `GITHUB_TOKEN`, `HF_TOKEN` and
  `PRODUCTHUNT_API_TOKEN` raise rate limits.
- **X** is off in the default workflow. It needs `uv sync --extra x`, `X_BEARER_TOKEN` and a list ID.
  The free API tier allows only about 100 post reads a month.

## Run it daily with GitHub Actions

`.github/workflows/daily.yml` runs every day at 02:17 UTC and on demand. Each run commits the new
issue to `archive/`, which also keeps GitHub from pausing the schedule. Public repositories get
GitHub Actions minutes for free.
Until an LLM key secret is set, the workflow finishes without doing anything, so a fresh copy never
fails or sends.

1. Use this repository as a template, or fork it and enable workflows in the Actions tab.
2. Add repository **secrets**: one LLM key (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`),
   `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`. Add publisher secrets as needed: `KIT_API_KEY`,
   `BUTTONDOWN_API_KEY`, `TELEGRAM_BOT_TOKEN`, `LLMDAILY_WEBHOOK_URL`. Optional: `HF_TOKEN`,
   `PRODUCTHUNT_API_TOKEN`.
3. Add repository **variables** as needed: `LLMDAILY_PUBLISHERS` (for example `archive,kit,telegram`),
   `LLMDAILY_LANG`, `LLMDAILY_PROVIDER`, `LLMDAILY_MODEL`, `LLMDAILY_EFFORT`, `OPENAI_BASE_URL`,
   `KIT_STATUS`, `TELEGRAM_CHAT_ID`, `LLMDAILY_SITE_URL`.
4. For the website, set **Settings › Pages › Source** to *GitHub Actions* and add the variable
   `LLMDAILY_PAGES=true`. The site is published at `https://<owner>.github.io/<repo>/`.
5. Run the workflow once from the Actions tab. Start with `KIT_STATUS=draft` and check the draft in
   Kit before switching to `send`.

## Project layout

```
config/sources.yaml          data source settings
llm_daily/cli.py             entry point (llm-daily / python -m llm_daily)
llm_daily/collectors/        one module per source, all subclass BaseCollector
llm_daily/generators/        section prompts and newsletter assembly
llm_daily/generators/validate.py   removes unsourced lines
llm_daily/llm/               provider layer: anthropic, openai-compatible, offline stub
llm_daily/publishers/        archive, kit, buttondown, telegram, webhook
llm_daily/site.py            static site and Atom feeds (llm-daily-site)
llm_daily/fixtures/          example data for --dry-run
archive/                     one Markdown file per issue, plus a JSON run record
tests/                       offline unit tests
```

## Development

```bash
uv sync --extra dev --extra openai --extra x
uv run pytest -q
uv run ruff check .
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for adding sources or providers.

## References

- [Anthropic API](https://docs.anthropic.com/en/api/) · [Kit API](https://developers.kit.com/) · [Buttondown API](https://docs.buttondown.com/)
- [PRAW](https://praw.readthedocs.io/) · [Reddit Data API terms](https://www.redditinc.com/policies/data-api-terms)
- [arXiv API](https://info.arxiv.org/help/api/index.html) · [X API](https://docs.x.com/x-api/introduction)

## License

MIT
