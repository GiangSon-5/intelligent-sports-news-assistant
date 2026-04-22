"""
A/B Testing — evaluator.py
Đánh giá chất lượng output AI theo nhiều tiêu chí.
Tính điểm tự động + hỗ trợ đánh giá thủ công (human review).
"""

import re
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EvaluationScore:
    """Kết quả đánh giá 1 output."""

    variant_name: str
    word_count: int = 0
    char_count: int = 0
    sentence_count: int = 0
    vietnamese_ratio: float = 0.0        # Tỷ lệ ký tự tiếng Việt
    has_required_structure: bool = False  # Đúng cấu trúc yêu cầu
    latency_ms: float = 0.0             # Thời gian xử lý
    token_usage: int = 0                 # Số tokens đã dùng
    auto_score: float = 0.0             # Điểm tự động (0-100)
    human_score: Optional[float] = None  # Điểm do người đánh giá (0-100)
    notes: str = ""                      # Ghi chú


class OutputEvaluator:
    """
    Đánh giá chất lượng output AI cho A/B Testing.

    Tiêu chí tự động:
    1. Word count (đúng range yêu cầu?)
    2. Sentence count (có đủ depth?)
    3. Vietnamese ratio (có viết đúng tiếng Việt?)
    4. Structure check (có format đúng?)
    5. Latency (nhanh hay chậm?)

    Usage:
        evaluator = OutputEvaluator()
        score = evaluator.evaluate_summary(
            output="Tuần qua, bóng đá Việt Nam...",
            variant_name="summary_concise",
            latency_ms=1200,
            target_word_range=(100, 150),
        )
    """

    # Ký tự tiếng Việt đặc trưng (dấu)
    _VIET_CHARS = set("àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ"
                      "ÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ")

    def evaluate_summary(
        self,
        output: str,
        variant_name: str,
        latency_ms: float = 0.0,
        token_usage: int = 0,
        target_word_range: tuple[int, int] = (200, 400),
    ) -> EvaluationScore:
        """
        Đánh giá Executive Summary output.

        Args:
            output: Text output từ AI
            variant_name: Tên variant đang test
            latency_ms: Thời gian xử lý (ms)
            token_usage: Số tokens dùng
            target_word_range: (min_words, max_words)

        Returns:
            EvaluationScore với auto_score 0-100
        """
        score = EvaluationScore(variant_name=variant_name)

        # Basic metrics
        score.char_count = len(output)
        words = output.split()
        score.word_count = len(words)
        score.sentence_count = len([s for s in re.split(r'[.!?。]', output) if s.strip()])
        score.latency_ms = latency_ms
        score.token_usage = token_usage

        # Vietnamese ratio
        viet_count = sum(1 for c in output if c in self._VIET_CHARS)
        total_alpha = sum(1 for c in output if c.isalpha())
        score.vietnamese_ratio = round(viet_count / max(total_alpha, 1), 3)

        # Structure check: summary phải là đoạn văn liền mạch
        score.has_required_structure = (
            score.sentence_count >= 3
            and "\n\n" not in output.strip()  # Không chia nhiều paragraph
            and score.word_count >= 50
        )

        # Auto score (0-100)
        points = 0.0

        # 1. Word count in range (30 pts)
        min_w, max_w = target_word_range
        if min_w <= score.word_count <= max_w:
            points += 30.0
        elif score.word_count < min_w:
            ratio = score.word_count / max(min_w, 1)
            points += 30.0 * min(ratio, 1.0)
        else:  # over max
            over = score.word_count - max_w
            penalty = min(over / max_w, 1.0)
            points += 30.0 * (1.0 - penalty * 0.5)

        # 2. Vietnamese content (25 pts)
        if score.vietnamese_ratio >= 0.05:
            points += 25.0
        elif score.vietnamese_ratio >= 0.02:
            points += 15.0
        else:
            points += 5.0

        # 3. Structure (20 pts)
        if score.has_required_structure:
            points += 20.0
        elif score.sentence_count >= 2:
            points += 10.0

        # 4. Depth — sentence count (15 pts)
        if score.sentence_count >= 5:
            points += 15.0
        elif score.sentence_count >= 3:
            points += 10.0
        elif score.sentence_count >= 1:
            points += 5.0

        # 5. Latency bonus (10 pts) — faster is better
        if latency_ms > 0:
            if latency_ms < 2000:
                points += 10.0
            elif latency_ms < 5000:
                points += 7.0
            elif latency_ms < 10000:
                points += 4.0
            else:
                points += 1.0

        score.auto_score = round(min(points, 100.0), 1)
        return score

    def evaluate_keywords(
        self,
        keywords: list[dict],
        variant_name: str,
        latency_ms: float = 0.0,
        expected_count: int = 15,
    ) -> EvaluationScore:
        """
        Đánh giá Keyword Extraction output.

        Args:
            keywords: list[{"keyword":..., "frequency":..., "category":...}]
            variant_name: Tên variant
            latency_ms: Thời gian xử lý
            expected_count: Số keywords mong đợi

        Returns:
            EvaluationScore
        """
        score = EvaluationScore(variant_name=variant_name)
        score.latency_ms = latency_ms
        score.word_count = len(keywords)

        points = 0.0

        # 1. Count match (30 pts)
        if len(keywords) == expected_count:
            points += 30.0
        else:
            ratio = len(keywords) / max(expected_count, 1)
            points += 30.0 * min(ratio, 1.0)

        # 2. Valid structure (25 pts)
        valid_categories = {"football", "basketball", "tennis", "esports",
                            "swimming", "athletics", "multi-sport", "other"}
        valid_count = 0
        for kw in keywords:
            has_keyword = bool(kw.get("keyword"))
            has_freq = isinstance(kw.get("frequency"), (int, float)) and kw["frequency"] > 0
            has_cat = kw.get("category") in valid_categories
            if has_keyword and has_freq and has_cat:
                valid_count += 1

        if keywords:
            structure_ratio = valid_count / len(keywords)
            points += 25.0 * structure_ratio
        score.has_required_structure = valid_count == len(keywords)

        # 3. Frequency sorted (20 pts)
        if len(keywords) >= 2:
            freqs = [kw.get("frequency", 0) for kw in keywords]
            is_sorted = all(freqs[i] >= freqs[i + 1] for i in range(len(freqs) - 1))
            if is_sorted:
                points += 20.0
            else:
                points += 8.0

        # 4. Diversity — category variety (15 pts)
        categories = {kw.get("category") for kw in keywords}
        if len(categories) >= 4:
            points += 15.0
        elif len(categories) >= 2:
            points += 10.0
        elif len(categories) >= 1:
            points += 5.0

        # 5. Latency (10 pts)
        if latency_ms > 0:
            if latency_ms < 3000:
                points += 10.0
            elif latency_ms < 8000:
                points += 6.0
            else:
                points += 2.0

        score.auto_score = round(min(points, 100.0), 1)
        return score

    @staticmethod
    def compare(score_a: EvaluationScore, score_b: EvaluationScore) -> dict:
        """
        So sánh 2 variants và đưa ra kết luận.

        Returns:
            dict: {"winner": str, "margin": float, "details": dict}
        """
        diff = score_a.auto_score - score_b.auto_score

        if abs(diff) < 3.0:
            winner = "TIE"
            verdict = "Hai variants cho kết quả tương đương"
        elif diff > 0:
            winner = score_a.variant_name
            verdict = f"{score_a.variant_name} tốt hơn {score_b.variant_name}"
        else:
            winner = score_b.variant_name
            verdict = f"{score_b.variant_name} tốt hơn {score_a.variant_name}"

        return {
            "winner": winner,
            "margin": round(abs(diff), 1),
            "verdict": verdict,
            "details": {
                score_a.variant_name: {
                    "auto_score": score_a.auto_score,
                    "word_count": score_a.word_count,
                    "latency_ms": score_a.latency_ms,
                    "vietnamese_ratio": score_a.vietnamese_ratio,
                },
                score_b.variant_name: {
                    "auto_score": score_b.auto_score,
                    "word_count": score_b.word_count,
                    "latency_ms": score_b.latency_ms,
                    "vietnamese_ratio": score_b.vietnamese_ratio,
                },
            },
        }
