"""
Pipeline Module — orchestrator.py
Central Orchestrator: Crawl → Store → Process → AI Analyze → Report.
According to SPEC §3.1-§3.4, supports step-by-step execution and CLI arguments.
"""

import os
import sys
import time
from datetime import datetime, timezone, timedelta

import pandas as pd

from logger import setup_logger, get_logger, log_function

_VN_TZ = timezone(timedelta(hours=7))


class PipelineOrchestrator:
    """
    Central orchestrator — coordinates the entire pipeline.
    Supports running the entire pipeline or individual steps.
    """

    def __init__(self, settings):
        self.settings = settings

        # Init logger (with 2-session rotation)
        self.logger = setup_logger(
            log_dir=settings.LOGS_DIR,
            level=settings.LOG_LEVEL,
        )

        # Lazy-loaded components (avoid heavy imports if not needed)
        self._store = None
        self._cleaner = None
        self._analyzer = None
        self._ai_orchestrator = None
        self._report_generator = None
        self._pdf_exporter = None

        # Runtime state
        self.processed_articles = None
        self.analysis = None
        self.ai_result = None

        # Result tracking
        self.result = {
            "status": "IDLE",
            "started_at": None,
            "completed_at": None,
            "duration_seconds": 0,
            "steps": {},
            "errors": [],
        }

        self.logger.info(
            f"PipelineOrchestrator initialized | env={settings.ENV} | log_level={settings.LOG_LEVEL}"
        )

    # ------------------------------------------------------------------
    #  Lazy Component Initialization
    # ------------------------------------------------------------------

    @property
    def store(self):
        if self._store is None:
            from storage.json_store import JsonFileStore
            self._store = JsonFileStore(base_dir="storage")
        return self._store

    @property
    def cleaner(self):
        if self._cleaner is None:
            from processing.cleaner import DataCleaner
            self._cleaner = DataCleaner(days_back=self.settings.CRAWL_DAYS_BACK)
        return self._cleaner

    @property
    def analyzer(self):
        if self._analyzer is None:
            from processing.analyzer import DataAnalyzer
            self._analyzer = DataAnalyzer()
        return self._analyzer

    @property
    def ai_orchestrator(self):
        if self._ai_orchestrator is None:
            from ai_engine.orchestrator import AIOrchestrator
            self._ai_orchestrator = AIOrchestrator(self.settings)
        return self._ai_orchestrator

    @property
    def report_generator(self):
        if self._report_generator is None:
            from reporting.markdown_generator import MarkdownReportGenerator
            self._report_generator = MarkdownReportGenerator()
        return self._report_generator

    @property
    def pdf_exporter(self):
        if self._pdf_exporter is None:
            from reporting.pdf_exporter import PdfExporter
            self._pdf_exporter = PdfExporter()
        return self._pdf_exporter

    # ------------------------------------------------------------------
    #  Main Run (SPEC §3.1)
    # ------------------------------------------------------------------

    @log_function("pipeline")
    def run(self, step: str = "all") -> dict:
        """
        Run pipeline — full or step-by-step.
        
        Args:
            step: "all" | "crawl" | "process" | "analyze" | "report"

        Returns:
            dict: Pipeline result with status and step details.
        """
        self.result["started_at"] = datetime.now(_VN_TZ).isoformat()
        self.logger.info(f"🚀 Pipeline started — step={step}, env={self.settings.ENV}")

        try:
            valid_steps = ("all", "crawl", "process", "analyze", "report")
            if step not in valid_steps:
                raise ValueError(f"Unknown pipeline step: {step}")

            if step in ("all", "crawl"):
                self._step_crawl()

            if step in ("all", "process"):
                self._step_process()

            if step in ("all", "analyze"):
                self._step_analyze()

            if step in ("all", "report"):
                self._step_report()

            # Determine final status
            failed_steps = [
                s for s, d in self.result["steps"].items()
                if d.get("status") == "FAILED"
            ]
            if failed_steps:
                self.result["status"] = "PARTIAL"
                self.logger.warning(f"⚠️ Pipeline partially completed. Failed steps: {failed_steps}")
            else:
                self.result["status"] = "COMPLETED"
                self.logger.info("✅ Pipeline completed successfully")

        except Exception as e:
            self.result["status"] = "FAILED"
            self.result["errors"].append(f"{type(e).__name__}: {str(e)}")
            self.logger.error(f"❌ Pipeline failed: {e}", exc_info=True)

        finally:
            self.result["completed_at"] = datetime.now(_VN_TZ).isoformat()
            self.result["duration_seconds"] = self._calc_duration()
            self._print_summary()

        return self.result

    # ------------------------------------------------------------------
    #  Step 1: CRAWL (SPEC §3.2)
    # ------------------------------------------------------------------

    def _step_crawl(self) -> None:
        """Step 1: Crawl news from 3 sources."""
        self.logger.info("📥 Step 1/4: CRAWL — Starting parallel crawl...")
        start = time.perf_counter()

        try:
            # Change CWD to crawler dir for Scrapy
            original_cwd = os.getcwd()
            crawler_dir = os.path.join(os.path.dirname(__file__), "..", "crawler")
            crawler_abs = os.path.abspath(crawler_dir)

            if crawler_abs not in sys.path:
                sys.path.insert(0, crawler_abs)

            from crawler.run import run_all_spiders
            crawl_result = run_all_spiders(self.settings)

            step_result = {
                "status": "SUCCESS",
                "duration_seconds": round(time.perf_counter() - start, 1),
                "articles_crawled": crawl_result.get("total_articles", 0),
                "sources_completed": crawl_result.get("sources_completed", []),
                "sources_failed": crawl_result.get("sources_failed", []),
            }

            if crawl_result.get("sources_failed"):
                self.logger.warning(
                    f"⚠️ Some sources failed: {crawl_result['sources_failed']}"
                )

        except Exception as e:
            step_result = {
                "status": "FAILED",
                "duration_seconds": round(time.perf_counter() - start, 1),
                "error": str(e),
            }
            self.logger.error(f"❌ Crawl failed: {e}", exc_info=True)
            raise

        self.result["steps"]["crawl"] = step_result
        self.logger.info(
            f"📥 Crawl done: {step_result.get('articles_crawled', 0)} articles "
            f"in {step_result['duration_seconds']}s"
        )

    # ------------------------------------------------------------------
    #  Step 2: PROCESS (SPEC §3.2)
    # ------------------------------------------------------------------

    def _step_process(self) -> None:
        """Step 2: Clean and analyze data."""
        self.logger.info("🔧 Step 2/4: PROCESS — Cleaning & analyzing data...")
        start = time.perf_counter()

        try:
            # Load raw data
            today = datetime.now(_VN_TZ).strftime("%Y-%m-%d")
            raw_articles = self.store.load_raw_articles(date=today)

            if not raw_articles:
                self.logger.warning("⚠️ No raw articles for today. Loading all raw files...")
                raw_articles = self.store.load_raw_articles()

            # Clean
            df = self.cleaner.clean(raw_articles)

            # Analyze
            self.analysis = self.analyzer.analyze(df)

            # Save processed
            self.processed_articles = df.to_dict("records")
            self.store.save_processed_articles(self.processed_articles, today)

            step_result = {
                "status": "SUCCESS",
                "duration_seconds": round(time.perf_counter() - start, 1),
                "articles_input": len(raw_articles),
                "articles_output": len(self.processed_articles),
                "articles_removed": len(raw_articles) - len(self.processed_articles),
            }

        except Exception as e:
            step_result = {
                "status": "FAILED",
                "duration_seconds": round(time.perf_counter() - start, 1),
                "error": str(e),
            }
            self.logger.error(f"❌ Process failed: {e}", exc_info=True)
            raise

        self.result["steps"]["process"] = step_result
        self.logger.info(
            f"🔧 Process done: {step_result.get('articles_input', 0)} → "
            f"{step_result.get('articles_output', 0)} articles "
            f"(removed {step_result.get('articles_removed', 0)})"
        )

    # ------------------------------------------------------------------
    #  Step 3: ANALYZE (SPEC §3.2)
    # ------------------------------------------------------------------

    def _step_analyze(self) -> None:
        """Step 3: AI processing (summarize, keywords, highlights)."""
        self.logger.info("🤖 Step 3/4: ANALYZE — AI processing with LangChain...")
        start = time.perf_counter()

        try:
            today = datetime.now(_VN_TZ).strftime("%Y-%m-%d")

            # Load from storage if running individual step
            if self.processed_articles is None:
                self.processed_articles = self.store.load_processed_articles(date=today)

                if not self.processed_articles:
                    self.processed_articles = self.store.load_processed_articles()

                if not self.processed_articles:
                    raise ValueError(
                        "No processed data found. Run --step process first."
                    )

                self.analysis = self.analyzer.analyze(
                    pd.DataFrame(self.processed_articles)
                )

            # Run AI processing
            self.ai_result = self.ai_orchestrator.process(
                articles=self.processed_articles,
                analysis=self.analysis,
            )

            # Persist AI result for the report step
            self.store.save_ai_result(self.ai_result, today)

            step_result = {
                "status": "SUCCESS",
                "duration_seconds": round(time.perf_counter() - start, 1),
                "model_used": self.ai_result.get("model_used", "unknown"),
                "fallback_triggered": self.ai_result.get("fallback_triggered", False),
                "tokens_used": self.ai_result.get("total_tokens_used", 0),
            }

        except Exception as e:
            step_result = {
                "status": "FAILED",
                "duration_seconds": round(time.perf_counter() - start, 1),
                "error": str(e),
            }
            self.logger.error(f"❌ AI Analysis failed: {e}", exc_info=True)
            raise

        self.result["steps"]["analyze"] = step_result
        self.logger.info(
            f"🤖 Analysis done: model={step_result.get('model_used', 'N/A')}, "
            f"fallback={step_result.get('fallback_triggered', False)}"
        )

    # ------------------------------------------------------------------
    #  Step 4: REPORT (SPEC §3.2)
    # ------------------------------------------------------------------

    def _step_report(self) -> None:
        """Step 4: Generate Markdown + PDF report."""
        self.logger.info("📊 Step 4/4: REPORT — Generating weekly report...")
        start = time.perf_counter()

        try:
            today = datetime.now(_VN_TZ).strftime("%Y-%m-%d")

            # Load AI result if running individual step
            if self.ai_result is None:
                self.ai_result = self.store.load_ai_result(date=today)

            if self.ai_result is None:
                raise ValueError(
                    "No AI analysis result found. Run --step analyze first."
                )

            if self.analysis is None:
                # Reload processed articles to restore metadata
                self.processed_articles = self.store.load_processed_articles(date=today)
                if not self.processed_articles:
                    self.processed_articles = self.store.load_processed_articles()
                
                if self.processed_articles:
                    self.analysis = self.analyzer.analyze(pd.DataFrame(self.processed_articles))
                else:
                    self.analysis = {
                        "total_articles": 0,
                        "date_range": {"from": "N/A", "to": "N/A"},
                        "articles_per_source": {},
                        "source_list": [],
                    }

            # Build report data
            report_data = {
                "ai_result": self.ai_result,
                "analysis": self.analysis,
                "report_metadata": {
                    "generated_at": datetime.now(_VN_TZ).isoformat(),
                    "report_version": "1.0",
                },
            }

            # Generate Markdown
            md_content = self.report_generator.generate(report_data)

            date_from = self.analysis.get("date_range", {}).get("from", "unknown")
            date_to = self.analysis.get("date_range", {}).get("to", "unknown")
            md_filename = f"weekly_report_{date_from}_{date_to}.md"
            md_path = self.store.save_report(md_content, md_filename)

            # Generate PDF (optional)
            pdf_path = None
            if self.pdf_exporter.is_available:
                try:
                    pdf_filename = f"weekly_report_{date_from}_{date_to}.pdf"
                    pdf_full_path = os.path.join("storage", "reports", pdf_filename)
                    pdf_path = self.pdf_exporter.export(md_content, pdf_full_path)
                except Exception as e:
                    self.logger.warning(f"⚠️ PDF export failed: {e}. Markdown is available.")
            else:
                self.logger.warning("⚠️ WeasyPrint not installed. PDF export skipped.")

            step_result = {
                "status": "SUCCESS",
                "duration_seconds": round(time.perf_counter() - start, 1),
                "markdown_path": md_path,
                "pdf_path": pdf_path,
            }

        except Exception as e:
            step_result = {
                "status": "FAILED",
                "duration_seconds": round(time.perf_counter() - start, 1),
                "error": str(e),
            }
            self.logger.error(f"❌ Report generation failed: {e}", exc_info=True)
            raise

        self.result["steps"]["report"] = step_result
        self.logger.info(
            f"📊 Report done: MD={step_result.get('markdown_path', 'N/A')}, "
            f"PDF={step_result.get('pdf_path', 'N/A')}"
        )

    # ------------------------------------------------------------------
    #  Utility Methods
    # ------------------------------------------------------------------

    def _calc_duration(self) -> float:
        """Calculate total pipeline duration."""
        try:
            from dateutil.parser import parse as parse_dt
            started = parse_dt(self.result["started_at"])
            completed = parse_dt(self.result["completed_at"])
            return round((completed - started).total_seconds(), 1)
        except Exception:
            # Fallback: sum step durations
            return sum(
                s.get("duration_seconds", 0)
                for s in self.result["steps"].values()
            )

    def _print_summary(self) -> None:
        """Print pipeline summary to console and log (Business Rule #5)."""
        steps_info = []
        for step_name, step_data in self.result["steps"].items():
            status = step_data.get("status", "UNKNOWN")
            duration = step_data.get("duration_seconds", 0)
            steps_info.append(f"{step_name}={status}({duration}s)")

        summary = (
            f"\n{'═' * 55}\n"
            f"  PIPELINE SUMMARY\n"
            f"  Status:   {self.result['status']}\n"
            f"  Duration: {self.result['duration_seconds']}s\n"
            f"  Steps:    {' | '.join(steps_info)}\n"
            f"  Errors:   {len(self.result['errors'])}\n"
            f"{'═' * 55}"
        )

        self.logger.info(summary)
        print(summary)
