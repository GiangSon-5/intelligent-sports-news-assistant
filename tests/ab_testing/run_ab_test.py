"""
A/B Testing — run_ab_test.py
CLI entry point để chạy các A/B experiments.

Usage:
    python -m tests.ab_testing.run_ab_test --type prompt --experiment summary_style
    python -m tests.ab_testing.run_ab_test --type model --experiment gemini_vs_gpt
    python -m tests.ab_testing.run_ab_test --report summary_style
    python -m tests.ab_testing.run_ab_test --list
"""

import argparse
import json
import os
import sys

# Ensure project root in sys.path
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def _load_sample_input() -> dict:
    """Load sample articles từ storage/processed/ hoặc tạo dummy data."""
    try:
        from storage.json_store import JsonFileStore
        store = JsonFileStore(base_dir="storage")
        articles = store.load_processed_articles()
        if articles:
            # Prepare summary input
            article_summaries = "\n\n".join([
                f"**{a.get('title', 'N/A')}** ({a.get('source', 'N/A')}, {a.get('publish_date', 'N/A')})\n{a.get('content', '')[:500]}"
                for a in articles[:5]  # Tiết kiệm tokens
            ])
            text_corpus = "\n".join([
                f"{a.get('title', '')}. {a.get('content', '')[:200]}"
                for a in articles[:10]  # Tiết kiệm tokens
            ])
            return {
                "article_summaries": article_summaries,
                "text_corpus": text_corpus,
                "total_articles": len(articles),
                "date_from": "N/A",
                "date_to": "N/A",
                "sources": "VnExpress, Thanh Niên, Tuổi Trẻ",
                "num_keywords": 15,
                "articles": articles,
            }
    except Exception:
        pass

    # Fallback: dummy data
    return {
        "article_summaries": (
            "**Đội tuyển Việt Nam thắng Thái Lan 2-1** (vnexpress, 2026-04-14)\n"
            "Trong trận đấu kịch tính tại sân Mỹ Đình, Nguyễn Tiến Linh ghi bàn quyết định phút 89.\n\n"
            "**V-League vòng 10: Hà Nội FC dẫn đầu** (thanhnien, 2026-04-15)\n"
            "CLB Hà Nội tiếp tục chuỗi 5 trận bất bại sau chiến thắng 3-0 trước SHB Đà Nẵng.\n\n"
            "**SEA Games 2026: Việt Nam đặt mục tiêu top 3** (tuoitre, 2026-04-16)\n"
            "Đoàn thể thao Việt Nam cử 500 VĐV tham dự SEA Games tại Campuchia."
        ),
        "text_corpus": (
            "Đội tuyển Việt Nam thắng Thái Lan 2-1 AFF Cup. "
            "V-League Hà Nội FC dẫn đầu bảng xếp hạng. "
            "SEA Games 2026 Campuchia Việt Nam top 3. "
            "Hoàng Đức Quả bóng Vàng Việt Nam 2026. "
        ),
        "total_articles": 50,
        "date_from": "2026-04-14",
        "date_to": "2026-04-20",
        "sources": "VnExpress, Thanh Niên, Tuổi Trẻ",
        "num_keywords": 10,
    }


def run_prompt_experiment(experiment_name: str) -> None:
    """Chạy Prompt A/B experiment."""
    from config.settings import get_settings
    from tests.ab_testing.experiment import ABExperiment
    from tests.ab_testing.variants import (
        PROMPT_SUMMARY_CONCISE,
        PROMPT_SUMMARY_DETAILED,
        PROMPT_SUMMARY_BULLET,
        PROMPT_KEYWORDS_STRICT,
        PROMPT_KEYWORDS_BROAD,
        PROMPT_CUSTOM_NEW_STYLE,
    )

    settings = get_settings()
    input_data = _load_sample_input()

    # Map experiment name → (variant_a, variant_b, parser, word_range)
    experiments = {
        "summary_style": {
            "a": PROMPT_SUMMARY_CONCISE,
            "b": PROMPT_SUMMARY_DETAILED,
            "parser": "str",
            "word_range": (100, 400),
            "desc": "Concise (100-150 từ) vs Detailed (300-400 từ)",
        },
        "summary_vs_bullet": {
            "a": PROMPT_SUMMARY_DETAILED,
            "b": PROMPT_SUMMARY_BULLET,
            "parser": "str",
            "word_range": (100, 400),
            "desc": "Paragraph summary vs Bullet-point summary",
        },
        "keyword_scope": {
            "a": PROMPT_KEYWORDS_STRICT,
            "b": PROMPT_KEYWORDS_BROAD,
            "parser": "json",
            "word_range": (10, 20),
            "desc": "Strict (chỉ tên riêng) vs Broad (tên riêng + chủ đề)",
        },
        "custom_genz": {
            "a": PROMPT_SUMMARY_CONCISE,
            "b": PROMPT_CUSTOM_NEW_STYLE,
            "parser": "str",
            "word_range": (100, 200),
            "desc": "Bình thường vs Phong cách GenZ (Thử nghiệm Custom)",
        },
    }

    if experiment_name not in experiments:
        print(f"❌ Unknown experiment: '{experiment_name}'")
        print(f"   Available: {', '.join(experiments.keys())}")
        return

    exp_config = experiments[experiment_name]
    print(f"\n🧪 A/B Prompt Test: {experiment_name}")
    print(f"   {exp_config['desc']}")
    print(f"   Variant A: {exp_config['a'].name}")
    print(f"   Variant B: {exp_config['b'].name}")
    print()

    exp = ABExperiment(name=experiment_name, settings=settings)
    result = exp.run_prompt_ab(
        variant_a=exp_config["a"],
        variant_b=exp_config["b"],
        input_data=input_data,
        output_parser=exp_config["parser"],
        target_word_range=exp_config["word_range"],
    )

    _print_result(result)


def run_model_experiment(experiment_name: str) -> None:
    """Chạy Model A/B experiment."""
    from config.settings import get_settings
    from tests.ab_testing.experiment import ABExperiment
    from tests.ab_testing.variants import (
        MODEL_GEMINI_FLASH,
        MODEL_GEMINI_FLASH_CREATIVE,
        MODEL_GEMINI_LITE,
        MODEL_GEMMA_4,
    )
    from ai_engine.prompts import EXECUTIVE_SUMMARY_PROMPT

    settings = get_settings()
    input_data = _load_sample_input()

    experiments = {
        "flash_vs_lite": {
            "a": MODEL_GEMINI_FLASH,
            "b": MODEL_GEMINI_LITE,
            "prompt": EXECUTIVE_SUMMARY_PROMPT,
            "desc": "Gemini 2.0 Flash vs Gemini 2.5 Flash Lite",
        },
        "gemini_temperature": {
            "a": MODEL_GEMINI_FLASH,
            "b": MODEL_GEMINI_FLASH_CREATIVE,
            "prompt": EXECUTIVE_SUMMARY_PROMPT,
            "desc": "Gemini temp=0.3 vs temp=0.7",
        },
        "flash_vs_gemma": {
            "a": MODEL_GEMINI_FLASH,
            "b": MODEL_GEMMA_4,
            "prompt": EXECUTIVE_SUMMARY_PROMPT,
            "desc": "Gemini 2.0 Flash vs Gemma 4 31B",
        },
    }

    if experiment_name not in experiments:
        print(f"❌ Unknown experiment: '{experiment_name}'")
        print(f"   Available: {', '.join(experiments.keys())}")
        return

    exp_config = experiments[experiment_name]
    print(f"\n🧪 A/B Model Test: {experiment_name}")
    print(f"   {exp_config['desc']}")
    print()

    exp = ABExperiment(name=experiment_name, settings=settings)
    result = exp.run_model_ab(
        variant_a=exp_config["a"],
        variant_b=exp_config["b"],
        prompt_template=exp_config["prompt"],
        input_data=input_data,
    )

    _print_result(result)


def show_report(experiment_name: str) -> None:
    """Hiển thị + lưu report cho experiment."""
    from tests.ab_testing.experiment import ABExperiment
    from unittest.mock import MagicMock

    exp = ABExperiment(name=experiment_name, settings=MagicMock())
    report = exp.generate_report()

    print(report)

    # Lưu ra file
    report_path = f"storage/ab_results/{experiment_name}_report.md"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n📄 Report saved: {report_path}")


def list_experiments() -> None:
    """Liệt kê tất cả experiments có sẵn."""
    print("\n🧪 A/B Testing — Available Experiments\n")

    print("📝 Prompt A/B Tests (--type prompt):")
    print("   summary_style       — Concise (100-150 từ) vs Detailed (300-400 từ)")
    print("   summary_vs_bullet   — Paragraph summary vs Bullet-point summary")
    print("   keyword_scope       — Strict (tên riêng) vs Broad (tên riêng + chủ đề)")
    print("   custom_genz         — Tóm tắt Bình thường vs Tóm tắt phong cách Gen-Z (Mới)")

    print("\n🤖 Model A/B Tests (--type model):")
    print("   flash_vs_lite       — Gemini 2.0 Flash vs Gemini 2.5 Flash Lite")
    print("   gemini_temperature  — Gemini temp=0.3 vs temp=0.7")
    print("   flash_vs_gemma      — Gemini 2.0 Flash vs Gemma 4 31B")

    print("\n📊 View report:")
    print("   --report <experiment_name>")


def _print_result(result) -> None:
    """In kết quả experiment ra terminal."""
    print(f"\n{'═' * 55}")
    print(f"  A/B TEST RESULT: {result.experiment_name}")
    print(f"{'═' * 55}")
    print(f"  Variant A: {result.variant_a_name}")
    print(f"    Score:   {result.variant_a_score}/100")
    print(f"    Latency: {result.variant_a_latency_ms}ms")
    print(f"  Variant B: {result.variant_b_name}")
    print(f"    Score:   {result.variant_b_score}/100")
    print(f"    Latency: {result.variant_b_latency_ms}ms")
    print(f"  ─────────────────────────────")
    print(f"  🏆 Winner: {result.winner} (margin: {result.margin})")
    print(f"  📋 Verdict: {result.verdict}")
    print(f"{'═' * 55}\n")


def main():
    parser = argparse.ArgumentParser(
        description="A/B Testing for Intelligent Sports News Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m tests.ab_testing.run_ab_test --list
    python -m tests.ab_testing.run_ab_test --type prompt --experiment summary_style
    python -m tests.ab_testing.run_ab_test --type model --experiment gemini_vs_gpt
    python -m tests.ab_testing.run_ab_test --report summary_style
        """,
    )
    parser.add_argument("--type", choices=["prompt", "model"], help="Loại experiment")
    parser.add_argument("--experiment", help="Tên experiment cụ thể")
    parser.add_argument("--report", help="Hiển thị report cho experiment")
    parser.add_argument("--list", action="store_true", help="Liệt kê experiments")

    args = parser.parse_args()

    if args.list:
        list_experiments()
    elif args.report:
        show_report(args.report)
    elif args.type and args.experiment:
        if args.type == "prompt":
            run_prompt_experiment(args.experiment)
        elif args.type == "model":
            run_model_experiment(args.experiment)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
