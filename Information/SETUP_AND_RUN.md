# 🚀 SETUP & RUN — Intelligent Sports News Assistant

Detailed guide to setting up and running the system from scratch.

---

## 1. Prerequisites (System Requirements)

| Requirement | Version | Notes |
|----------|-----------|---------|
| **Python** | ≥ 3.10 | Recommended 3.11+ |
| **pip** | ≥ 23.0 | Package manager |
| **Git** | Any | To clone the project |
| **Internet** | Mandatory | For crawling + AI API calls |
| **API Key: Gemini** | Mandatory | https://aistudio.google.com/apikey |
| **API Key: OpenAI** | Recommended | https://platform.openai.com/api-keys (for fallback) |
| **GTK+ / Pango** | Optional | Only needed if exporting PDF via WeasyPrint |

### Installing WeasyPrint on Windows (Optional — for PDF export only):
```powershell
# Install MSYS2 → add GTK runtime
# Or skip if you only need Markdown reports
pip install WeasyPrint
```

---

## 2. Installation

```bash
# Clone project (or copy folder)
cd "C:\path\to\your\project"

# Create virtual environment
python -m venv .venv

# Activate venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Windows CMD:
.venv\Scripts\activate.bat
# Linux/Mac:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install project as an editable package (for cross-module imports)
pip install -e .
```

---

## 3. Environment Setup

```bash
# Copy template
cp .env.example .env

# Open .env file and fill in API keys
```

### Content of `.env` file to be edited:

```env
# === MANDATORY ===
GEMINI_API_KEY=AIzaSy...your_gemini_key_here...

# === RECOMMENDED (for fallback when Gemini fails) ===
OPENAI_API_KEY=sk-...your_openai_key_here...
ENABLE_FALLBACK=true

# === CUSTOMIZATION (keep defaults if unsure) ===
PRIMARY_MODEL=gemini-2.0-flash
FALLBACK_MODEL=gpt-4o
CONCURRENT_REQUESTS=16
DOWNLOAD_DELAY=0.5
CRAWL_DAYS_BACK=7
ENV=DEV
LOG_LEVEL=INFO
```

### Important Variables:

| Variable | Mandatory | Description |
|------|----------|-------|
| `GEMINI_API_KEY` | ✅ Yes | Google Gemini API key. Without this → system won't run |
| `OPENAI_API_KEY` | ⚠️ Yes* | OpenAI API key. *Mandatory if `ENABLE_FALLBACK=true` |
| `ENABLE_FALLBACK` | No | `true` (default) = automatically switch to OpenAI when Gemini fails |
| `CONCURRENT_REQUESTS` | No | Number of concurrent requests when crawling (1-64, default 16) |
| `CRAWL_DAYS_BACK` | No | Number of days to look back for data collection (1-30, default 7) |
| `ENV` | No | `DEV` or `PRODUCTION`. Production increases crawl delay to 1.0s |
| `LOG_LEVEL` | No | `DEBUG`, `INFO`, `WARNING`, `ERROR` (default INFO) |

---

## 4. Running the Project

### 4.1 Run the full pipeline (recommended):
```bash
python main.py
```

### 4.2 Run individual steps:
```bash
# Step 1: Only crawl news
python main.py --step crawl

# Step 2: Only process/clean data
python main.py --step process

# Step 3: Only run AI analysis
python main.py --step analyze

# Step 4: Only generate report
python main.py --step report
```

### 4.3 Run with debug logging:
```bash
python main.py --verbose
```

### 4.4 Output Results:
After the execution process is complete, the system will generate the following results:
```
storage/reports/
├── weekly_report_2026-04-14_2026-04-20.md    ← Markdown report (MANDATORY)
└── weekly_report_2026-04-14_2026-04-20.pdf   ← PDF report (if WeasyPrint is installed)
```

### 4.5 Run automatically with Airflow & Docker (Ops Mode):
If you want the system to automatically run periodically in the background (6:00 AM every day), the project has pre-integrated a professional MLOps architecture using **Apache Airflow**.

**A. Launch Steps:**
```bash
# 1. Download and build configuration (Only done once or when requirements.txt is modified)
docker-compose build

# 2. Initialize Database for Airflow (Only done once)
docker-compose run --rm airflow-scheduler airflow db migrate

# 3. Create login account (Only done once)
docker-compose run --rm airflow-scheduler airflow users create --role Admin --username admin --password admin --email admin@system.com --firstname Admin --lastname User

# 4. Activate the entire system in the background
docker-compose up -d
```
After successful launch, access **http://localhost:8080** (username: `admin` / password: `admin`), find the DAG `sports_news_pipeline` and turn the Toggle switch to green.

**B. Safe Cleanup (Clean-up):**
When you no longer need Airflow and want to free up computer resources, use the following command to **ONLY** delete the components of this project (WITHOUT affecting other Docker projects of the company):

```bash
# Only stop the Airflow servers (database remains)
docker-compose down

# STOP AND CLEAR EVERYTHING (Clear All) including Containers, Networks, and the project's own Image:
docker-compose down -v --rmi local
```
*(The `down -v --rmi local` command will use the `docker-compose.yml` file to target precisely. News data in the `./storage` folder remains preserved).*

---

## 5. Logging & Debugging (2-Version Log System)

### 5.1 Log File Locations:
```
logs/
├── current_run.log.json     ← Log of the CURRENT run
└── previous_run.log.json    ← Log of the PREVIOUS run
```

### 5.2 Rotation Mechanism:
When executing the data update process (`python main.py`):
1. ❌ Old `previous_run.log.json` is **DELETED**
2. 📝 `current_run.log.json` is **RENAMED** to `previous_run.log.json`
3. ✨ A **NEW** `current_run.log.json` is created (empty)

→ Always keeps exactly **2 log files**: the current session + the previous session.

### 5.3 Log Format (JSON):
Each line in the log file is a JSON object:
```json
{
    "timestamp": "2026-04-20T06:00:01+07:00",
    "level": "INFO",
    "logger": "sports_assistant.crawler",
    "module": "vnexpress_spider",
    "function": "parse_article",
    "line": 85,
    "message": "Article #15 parsed | title='Đội tuyển VN...' | chars=523 | latency=12.5ms",
    "input": {"arg_0": "https://vnexpress.net/..."},
    "output": "NewsArticleItem",
    "latency_ms": 12.5
}
```

### 5.4 How to Debug:
```bash
# View current run log (PowerShell)
Get-Content logs/current_run.log.json | ConvertFrom-Json | Format-Table timestamp, level, message

# Find errors in log
Select-String "ERROR" logs/current_run.log.json

# Compare current vs previous run
# → Open both files in VS Code to compare
```

---

## 6. Project Structure

```
sports_ai_project/
├── main.py                       # Entry point
├── .env                          # API keys (SELF-CREATED from .env.example)
├── .env.example                  # Environment variable template
├── requirements.txt              # Python dependencies
├── setup.py                      # Package setup
├── logger.py                     # Base Logger (2-session rotation)
│
├── config/                       # Configuration management
│   ├── __init__.py
│   └── settings.py               # Pydantic Settings
│
├── crawler/                      # Data collection (Scrapy)
│   ├── scrapy.cfg
│   ├── run.py                    # Runs 3 spiders in parallel
│   └── news_crawler/
│       ├── items.py              # Article schema
│       ├── settings.py           # Scrapy settings
│       ├── middlewares.py        # Custom middlewares
│       ├── pipelines.py          # 4 pipelines (validate→date→dedup→export)
│       └── spiders/
│           ├── vnexpress_spider.py
│           ├── thanhnien_spider.py
│           └── tuoitre_spider.py
│
├── storage/                      # JSON Storage
│   ├── json_store.py             # Repository Pattern
│   ├── raw/                      # Raw data
│   ├── processed/                # Cleaned data
│   └── reports/                  # MD/PDF Reports
│
├── processing/                   # Data processing (Pandas)
│   ├── cleaner.py                # 6-step cleaning pipeline
│   └── analyzer.py               # Statistics
│
├── ai_engine/                    # AI/NLP (LangChain)
│   ├── orchestrator.py           # Gemini + OpenAI fallback
│   └── prompts.py                # Prompt templates
│
├── reporting/                    # Report generation
│   ├── markdown_generator.py     # Jinja2 → Markdown
│   ├── pdf_exporter.py           # Markdown → PDF
│   └── templates/
│       └── weekly_report.md.j2   # Jinja2 template
│
├── pipeline/                     # Central Orchestrator
│   └── orchestrator.py           # Crawl → Process → AI → Report
│
├── tests/                        # Unit tests + A/B testing
│   ├── conftest.py               # Shared fixtures
│   ├── test_config.py            # Config validation tests
│   ├── test_storage.py           # Storage CRUD tests
│   ├── test_crawler.py           # Crawler pipeline tests
│   ├── test_processing.py        # Cleaning/analyzer tests
│   ├── test_ai_engine.py         # AI orchestrator tests
│   ├── test_reporting.py         # Report generation tests
│   ├── test_pipeline.py          # Pipeline + logger tests
│   └── ab_testing/               # A/B Testing framework
│       ├── variants.py           # Prompt/Model variants
│       ├── evaluator.py          # Output scoring
│       ├── experiment.py         # Experiment engine
│       └── run_ab_test.py        # CLI entry point
├── logs/                         # Runtime logs (2-session rotation)
└── docs/                         # SPEC & SRS files (in each module)
```

---

## 7. Troubleshooting

| Issue | Cause | Solution |
|---------|-------------|-----------|
| `ValidationError: GEMINI_API_KEY is required` | Missing API key | Create `.env` file, fill in `GEMINI_API_KEY` |
| `ValidationError: OPENAI_API_KEY required when...` | Fallback enabled but missing OpenAI key | Fill in `OPENAI_API_KEY` or set `ENABLE_FALLBACK=false` |
| `ModuleNotFoundError: No module named 'config'` | Editable package not installed | Run `pip install -e .` |
| `ModuleNotFoundError: No module named 'scrapy'` | Dependencies not installed | Run `pip install -r requirements.txt` |
| Crawled 0 articles | Website changed HTML | Check selectors in spiders, update CSS/XPath |
| AI analysis empty | API key expired / quota | Check API key, see ERROR log in `current_run.log.json` |
| PDF cannot be created | WeasyPrint not installed | `pip install WeasyPrint` + install GTK system deps |
| Log file too large | Run many times consecutively | System self-deletes — always keeps only 2 log files |

---

## 8. Automation & A/B Testing

The entire operational testing system (High coverage Automation Unit Tests) periodically and setting up extended trial features (A/B Testing on LLM configurations, Prompts) has been separated and the process standardized into an independent document.

> **Detailed Documentation:**
> Please refer to the software quality inspection standard set in the following professional document: 
> 👉 **[TESTING_GUIDE.md](TESTING_GUIDE.md)**
