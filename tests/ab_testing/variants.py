"""
A/B Testing — variants.py
Định nghĩa các biến thể (variants) cho thí nghiệm A/B.
Hỗ trợ 3 loại variant: Prompt, Model, Parameter.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PromptVariant:
    """
    Biến thể Prompt — so sánh hiệu quả tóm tắt giữa các prompt khác nhau.

    Usage:
        variant_a = PromptVariant(
            name="concise_vi",
            prompt_template="Tóm tắt ngắn gọn...",
            description="Prompt tiếng Việt, yêu cầu ngắn gọn 100 từ"
        )
    """

    name: str                       # Tên variant (unique ID)
    prompt_template: str            # Nội dung prompt
    description: str = ""           # Mô tả ngắn gọn
    tags: list[str] = field(default_factory=list)  # Tags phân loại

    def __post_init__(self):
        if not self.name:
            raise ValueError("PromptVariant.name cannot be empty")
        if not self.prompt_template:
            raise ValueError("PromptVariant.prompt_template cannot be empty")


@dataclass
class ModelVariant:
    """
    Biến thể Model — so sánh output giữa các LLM khác nhau.

    Usage:
        variant_a = ModelVariant(
            name="gemini_flash",
            provider="google",
            model_name="gemini-2.0-flash",
            temperature=0.3,
        )
    """

    name: str                       # Tên variant (unique ID)
    provider: str                   # "google" | "openai"
    model_name: str                 # Tên model cụ thể
    temperature: float = 0.3        # Nhiệt độ sampling
    max_tokens: int = 1024          # Max output tokens
    description: str = ""           # Mô tả

    def __post_init__(self):
        if self.provider not in ("google", "openai"):
            raise ValueError(f"Provider must be 'google' or 'openai', got: {self.provider}")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError(f"Temperature must be 0.0-2.0, got: {self.temperature}")


# ---------------------------------------------------------------------------
#  Predefined Variants (Sẵn sàng dùng)
# ---------------------------------------------------------------------------

# --- Prompt Variants: Executive Summary ---

PROMPT_SUMMARY_CONCISE = PromptVariant(
    name="summary_concise",
    description="Tóm tắt ngắn gọn 100-150 từ, ưu tiên sự kiện chính",
    tags=["summary", "concise"],
    prompt_template="""Bạn là nhà phân tích thể thao. Tóm tắt các tin tức sau thành 1 đoạn văn NGẮN GỌN (100-150 từ).
Chỉ nêu 3 sự kiện quan trọng nhất. Không dùng bullet points.

**Tin tức:**
{article_summaries}

**Output:** 1 đoạn văn 100-150 từ bằng tiếng Việt."""
)

PROMPT_SUMMARY_DETAILED = PromptVariant(
    name="summary_detailed",
    description="Tóm tắt chi tiết 300-400 từ, phân tích xu hướng",
    tags=["summary", "detailed"],
    prompt_template="""Bạn là nhà phân tích thể thao chuyên nghiệp. Viết Executive Summary chi tiết (300-400 từ) bằng tiếng Việt.

**Yêu cầu:**
1. Bức tranh chung của thể thao tuần qua
2. Phân tích 3-5 xu hướng nổi bật
3. Nhận định và dự đoán ngắn hạn
4. Phong cách chuyên nghiệp, có depth

**Thống kê:** {total_articles} bài | Kỳ: {date_from} — {date_to} | Nguồn: {sources}

**Tổng hợp tin tức:**
{article_summaries}

**Output:** Đoạn văn Executive Summary 300-400 từ."""
)

PROMPT_SUMMARY_BULLET = PromptVariant(
    name="summary_bullet",
    description="Tóm tắt dạng bullet points, dễ scan nhanh",
    tags=["summary", "bullet"],
    prompt_template="""Bạn là biên tập viên thể thao. Tóm tắt tin tức tuần qua thành danh sách bullet points (tiếng Việt).

**Format:**
- Mỗi bullet là 1 sự kiện quan trọng (1-2 câu)
- Tối đa 7-10 bullets
- Sắp xếp theo mức độ quan trọng giảm dần
- Đầu mỗi bullet ghi nguồn [VnExpress] / [Thanh Niên] / [Tuổi Trẻ]

**Tin tức:**
{article_summaries}

**Output:** Danh sách bullet points."""
)

# --- Prompt Variants: Keyword Extraction ---

PROMPT_KEYWORDS_STRICT = PromptVariant(
    name="keywords_strict",
    description="Trích xuất keyword chỉ từ proper nouns (tên riêng)",
    tags=["keywords", "strict"],
    prompt_template="""Trích xuất {num_keywords} TÊN RIÊNG nổi bật nhất (người, giải đấu, đội bóng, địa điểm) từ corpus tin tức thể thao.

**Corpus:** {text_corpus}

**Output JSON:**
{{"keywords": [{{"keyword": "tên riêng", "frequency": số_lần, "category": "football|tennis|esports|other"}}]}}

Chỉ lấy TÊN RIÊNG, không lấy danh từ chung. Output JSON thuần."""
)

PROMPT_KEYWORDS_BROAD = PromptVariant(
    name="keywords_broad",
    description="Trích xuất keyword rộng: tên riêng + chủ đề + xu hướng",
    tags=["keywords", "broad"],
    prompt_template="""Trích xuất {num_keywords} từ khóa/chủ đề nổi bật nhất từ corpus tin tức thể thao.
Bao gồm cả: tên riêng, giải đấu, xu hướng, chủ đề nóng.

**Corpus:** {text_corpus}

**Output JSON:**
{{"keywords": [{{"keyword": "từ khóa", "frequency": số_lần, "category": "football|basketball|tennis|esports|swimming|athletics|multi-sport|other"}}]}}

Sắp xếp giảm dần theo frequency. Output JSON thuần."""
)

# Ví dụ thêm custom prompt mới:
PROMPT_CUSTOM_NEW_STYLE = PromptVariant(
    name="summary_custom_genz",
    description="Tóm tắt với phong cách GenZ trẻ trung, vui nhộn",
    tags=["summary", "genz"],
    prompt_template="""Bạn là một Tiktok-er thể thao. Tóm tắt nội dung sau theo phong cách Gen-Z, dùng các từ lóng vui vẻ, độ dài khoảng 100 từ.
    
**Tin tức:**
{article_summaries}

**Output:** 1 đoạn văn tiếng Việt chuẩn Gen Z."""
)

# --- Model Variants ---

MODEL_GEMINI_FLASH = ModelVariant(
    name="gemini_flash",
    provider="google",
    model_name="gemini-2.0-flash",
    temperature=0.3,
    max_tokens=1024,
    description="Gemini 2.0 Flash — nhanh, rẻ",
)

MODEL_GEMINI_FLASH_CREATIVE = ModelVariant(
    name="gemini_flash_creative",
    provider="google",
    model_name="gemini-2.0-flash",
    temperature=0.7,
    max_tokens=1024,
    description="Gemini 2.0 Flash — temperature cao hơn cho output đa dạng",
)

MODEL_GEMINI_LITE = ModelVariant(
    name="gemini_lite",
    provider="google",
    model_name="gemini-2.5-flash-lite",
    temperature=0.3,
    max_tokens=1024,
    description="Gemini 2.5 Flash Lite — cực nhẹ, siêu rẻ",
)

MODEL_GEMMA_4 = ModelVariant(
    name="gemma_4",
    provider="google",
    model_name="gemma-4-31b-it",
    temperature=0.3,
    max_tokens=1024,
    description="Gemma 4 31B — model mã nguồn mở mới nhất trên vertex",
)

# ---------------------------------------------------------------------------
#  Registry — truy cập nhanh tất cả variants
# ---------------------------------------------------------------------------

ALL_PROMPT_VARIANTS = {
    v.name: v
    for v in [
        PROMPT_SUMMARY_CONCISE,
        PROMPT_SUMMARY_DETAILED,
        PROMPT_SUMMARY_BULLET,
        PROMPT_KEYWORDS_STRICT,
        PROMPT_KEYWORDS_BROAD,
        PROMPT_CUSTOM_NEW_STYLE,
    ]
}

ALL_MODEL_VARIANTS = {
    v.name: v
    for v in [
        MODEL_GEMINI_FLASH,
        MODEL_GEMINI_FLASH_CREATIVE,
        MODEL_GEMINI_LITE,
        MODEL_GEMMA_4,
    ]
}
