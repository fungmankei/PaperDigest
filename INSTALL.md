# Installation

## Requirements

- Python **3.10+** (tested on 3.12/3.13).
- Internet access for the CrossRef API.

## 1. Get the code

```bash
git clone <your-fork-url> weekly_journal_digest
cd weekly_journal_digest
```

## 2. Create a virtual environment (recommended)

macOS / Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## 3. Install core dependencies

```bash
pip install -r requirements.txt
```

This installs the zero-cost baseline: PyYAML, requests, BeautifulSoup,
scikit-learn, numpy.

## 4. Optional: reading `.xlsx` ranking files

If your combined ranking file is an Excel workbook:

```bash
pip install openpyxl
```

## 5. Optional: AI mode (local / free)

Semantic similarity via local embeddings:

```bash
pip install sentence-transformers
```

Local LLM summaries via [Ollama](https://ollama.com):

```bash
# install ollama (see ollama.com), then:
ollama pull llama3.2
ollama serve            # keep running; the digest calls http://localhost:11434
```

Set in `config/user_config.yaml`:

```yaml
ai_settings:
  use_ai_agents: true
  embedding_model: "all-MiniLM-L6-v2"
  llm_provider: "ollama"
  llm_model: "llama3.2"
```

### Hosted / paid LLM providers

No extra Python packages are needed — every provider is called over HTTP. Supply
the model and an API key (prefer the env var `DIGEST_LLM_API_KEY`).

```yaml
# OpenAI
ai_settings: { use_ai_agents: true, llm_provider: openai,    llm_model: gpt-4o-mini }
# Anthropic (Claude)
ai_settings: { use_ai_agents: true, llm_provider: anthropic, llm_model: claude-3-5-haiku-latest }
# Google Gemini
ai_settings: { use_ai_agents: true, llm_provider: gemini,    llm_model: gemini-1.5-flash }
# Presets (base URL is filled in for you): openrouter | together | groq | deepseek | fireworks
ai_settings: { use_ai_agents: true, llm_provider: groq,      llm_model: llama-3.1-8b-instant }
```

```bash
export DIGEST_LLM_API_KEY="sk-..."     # Windows: setx DIGEST_LLM_API_KEY "sk-..."
```

### Any other OpenAI-compatible endpoint

Use `llm_provider: custom` and set `llm_base_url` (e.g. Azure OpenAI gateways,
vLLM / LM Studio, or any service exposing `/chat/completions`):

```yaml
ai_settings:
  use_ai_agents: true
  llm_provider: custom
  llm_base_url: "https://your-endpoint/v1"
  llm_model: "your-model-name"
  # llm_api_key via DIGEST_LLM_API_KEY (optional for keyless local servers)
```

## 6. Verify

```bash
python -m src.journal_registry            # counts journals in data/journals.csv
python -m src.main --dry-run --no-email   # runs the pipeline, prints the digest
```

If `data/journals.csv` is missing, start from the sample:

```bash
cp data/journals.sample.csv data/journals.csv   # Windows: copy
```
