"""
Intelligent Sports News Assistant — Main Entry Point
Usage:
    python main.py                    # Run full pipeline for today
    python main.py --step crawl       # Only crawl
    python main.py --step process     # Only process data
    python main.py --step analyze --date 2026-05-04  # Specific date
    python main.py --step report  --date 2026-05-01:2026-05-07 # Date range
    python main.py --verbose          # Enable debug logging
"""

import argparse
import sys


def main() -> int:
    """Main entry point — parse CLI args, init config, run pipeline."""

    # --- Parse CLI Arguments (Pipeline SPEC §2.3) ---
    parser = argparse.ArgumentParser(
        description="Intelligent Sports News Assistant - Pipeline Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # 1. Run the entire pipeline for today (Crawl -> Process -> Analyze -> Report)
    python main.py                     

    # 2. Run a specific individual step
    python main.py --step crawl        # Only crawl new articles
    python main.py --step process      # Only clean and filter raw data
    python main.py --step analyze      # Only run AI analysis
    python main.py --step report       # Only generate final report

    # 3. Work with historical data (Specific Date)
    python main.py --step process --date 2026-05-04         # Re-process raw data from May 4th
    python main.py --step analyze --date 2026-05-04         # Analyze data from May 4th

    # 4. Generate summary reports (Date Range)
    # Syntax: --date YYYY-MM-DD:YYYY-MM-DD
    python main.py --step process --date 2026-05-01:2026-05-07  # Process all raw files of the week
    python main.py --step report  --date 2026-05-01:2026-05-07  # Weekly summary report

    # 5. Technical debug mode
    python main.py --verbose           # Show detailed debug logs
        """,
    )
    parser.add_argument(
        "--step",
        choices=["crawl", "process", "analyze", "report", "all"],
        default="all",
        help="Run specific pipeline step (default: all)",
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Target date (YYYY-MM-DD) or range (YYYY-MM-DD:YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level)",
    )
    args = parser.parse_args()

    # --- Load Config (fail-fast) ---
    try:
        from config.settings import get_settings

        settings = get_settings()
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        print("   Check your .env file. See .env.example for template.")
        return 1

    # --- Override log level if --verbose ---
    if args.verbose:
        settings.LOG_LEVEL = "DEBUG"

    # --- Run Pipeline ---
    from pipeline.orchestrator import PipelineOrchestrator

    orchestrator = PipelineOrchestrator(settings)
    result = orchestrator.run(step=args.step, target_date=args.date)

    # Return exit code based on status
    if result["status"] == "COMPLETED":
        return 0
    elif result["status"] == "PARTIAL":
        return 0  # Partial is OK — some sources may fail
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
