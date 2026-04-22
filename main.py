"""
Intelligent Sports News Assistant — Main Entry Point
Usage:
    python main.py                    # Run full pipeline
    python main.py --step crawl       # Only crawl
    python main.py --step process     # Only process data
    python main.py --step analyze     # Only run AI analysis
    python main.py --step report      # Only generate report
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
    python main.py                     Run full pipeline
    python main.py --step crawl        Only crawl news
    python main.py --step process      Only process/clean data
    python main.py --step analyze      Only run AI analysis
    python main.py --step report       Only generate report
    python main.py --verbose           Enable DEBUG logging
        """,
    )
    parser.add_argument(
        "--step",
        choices=["crawl", "process", "analyze", "report", "all"],
        default="all",
        help="Run specific pipeline step (default: all)",
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
    result = orchestrator.run(step=args.step)

    # Return exit code based on status
    if result["status"] == "COMPLETED":
        return 0
    elif result["status"] == "PARTIAL":
        return 0  # Partial is OK — some sources may fail
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
