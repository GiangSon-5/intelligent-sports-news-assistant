# Testing Guide (Automation Test & A/B Testing)

This document provides comprehensive testing standards, including the process for running Automation Tests (Unit Tests) to verify the system and setting up A/B Testing scenarios to compare parameters of different AI models and prompts.

---

## Part 1: Automation Testing

The automated testing process uses `pytest` to ensure the entire system operates stably and safely. Tests simulate (mock) all API call methods and do not require API keys to function.

### 1.1 Run the full test suite:
```bash
pytest
```

### 1.2 Run tests by module:
```bash
# Test Config module (configuration validation)
pytest tests/test_config.py -v

# Test Storage module (storage operations)
pytest tests/test_storage.py -v

# Test Crawler module (items, pipelines, date processing)
pytest tests/test_crawler.py -v

# Test Processing module (cleaner + analyzer)
pytest tests/test_processing.py -v

# Test AI Engine module (prompts, AI orchestrator process)
pytest tests/test_ai_engine.py -v

# Test Reporting module (export and report generation)
pytest tests/test_reporting.py -v

# Test Pipeline + Logger system (central orchestration)
pytest tests/test_pipeline.py -v
```

### 1.3 Run tests with Code Coverage:
```bash
pytest --cov=config --cov=storage --cov=processing --cov=ai_engine --cov=reporting --cov=pipeline -v
```

---

## Part 2: A/B Testing Algorithms for AI

The A/B Testing framework allows for accurate evaluation and comparison of performance between different **prompts**, **AI models**, and **parameters**.

> **Note:** The A/B Testing process **requires** using API keys (configured in `.env`) to interact directly with the LLM and generate accurate comparative data.

### 2.1 List pre-configured tests:
```bash
# View list of all runnable tests
python -m tests.ab_testing.run_ab_test --list

# View help for command parameters
python -m tests.ab_testing.run_ab_test --help
```

### 2.2 Run Prompt A/B Test (Same model, different prompt configurations):
Used to optimize how AI writes content.

```bash
# 1. Compare Concise Summary (100 words) vs Detailed Summary (300 words)
python -m tests.ab_testing.run_ab_test --type prompt --experiment summary_style

# 2. Compare Paragraph Summary vs Bullet points
python -m tests.ab_testing.run_ab_test --type prompt --experiment summary_vs_bullet

# 3. Compare Keyword Extraction: Narrow scope (strict) vs Extended scope (rich)
python -m tests.ab_testing.run_ab_test --type prompt --experiment keyword_scope

# 4. Experiment with Gen-Z writing style (New custom style)
python -m tests.ab_testing.run_ab_test --type prompt --experiment custom_genz
```

### 2.3 Run Model A/B Test (Same prompt, different models / parameter configurations):
Used to select the fastest and cheapest AI model while ensuring quality.

```bash
# 1. Compare Gemini 2.0 Flash with optimized Gemini 2.5 Flash Lite
python -m tests.ab_testing.run_ab_test --type model --experiment flash_vs_lite

# 2. Evaluate impact of Creativity (Temperature): 0.3 vs 0.7
python -m tests.ab_testing.run_ab_test --type model --experiment gemini_temperature

# 3. Compare Gemini 2.0 Flash with open-source Gemma 4 31B
python -m tests.ab_testing.run_ab_test --type model --experiment flash_vs_gemma
```

### 2.4 View Summary Report & Results:
```bash
# View win/loss results directly on the Terminal
python -m tests.ab_testing.run_ab_test --report summary_style
```

The testing process will automatically generate a JSON report containing metrics and aggregate details into a `report.md` file in the `storage/ab_results/` directory. The system applies 5 criteria for automated scoring (100-point scale).

---

## Part 3: Customizing & Editing Tests

The system is designed so that operators can easily change experimental content without rewriting complex logic.

### 3.1 Where to edit content (Prompts & Model Settings)
All experimental "ingredients" are located at:
👉 **`tests/ab_testing/variants.py`**

*   **To edit AI wording:** Find the `PROMPT_...` variables. You can edit the requirement content within the `prompt_template`.
*   **Example:** If you want to change the **Gen-Z** scenario to a **CEO** style, find the `PROMPT_CUSTOM_NEW_STYLE` variable and edit the template to: *"Act as an elegant CEO, summarize this news professionally using business language..."*

### 3.2 Where to edit "Matchups"
To change the comparison subjects (e.g., compare variant A with variant C instead of variant B), access:
👉 **`tests/ab_testing/run_ab_test.py`**

Find the `experiments` list (line 93 for Prompt or line 163 for Model).
*   **How to change:** Simply change the value of `"a"` or `"b"` with the names of the variables defined in `variants.py`.

### 3.3 Practical Example: Customizing the "Creativity" test
Suppose you need to increase the creativity level (Temperature) from 0.7 to 0.9 to check AI output quality:

1.  Open file `tests/ab_testing/variants.py`.
2.  Find the variable `MODEL_GEMINI_FLASH_CREATIVE`.
3.  Change `temperature=0.7` to `temperature=0.9`.
4.  Save the file and rerun the command in the Terminal:
    ```bash
    python -m tests.ab_testing.run_ab_test --type model --experiment gemini_temperature
    ```

### 3.4 Note on API Rate Limits
When running A/B Tests continuously, the system may encounter `Rate limit hit!` warnings. Consider increasing `A_B_TEST_DELAY` or checking your API quota.
*   Avoid interrupting the process with manual commands: Let the system handle itself during the countdown.
*   Interrupting midway will skew the scoring results of the AI "referee".

---
👉 **Note:** After editing any `.py` file, simply save the file and rerun the test command immediately to record changes.
