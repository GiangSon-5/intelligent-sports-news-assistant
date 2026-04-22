"""
AI Engine Module — prompts.py
Prompt templates for LLM according to SPEC §5.1-§5.4.
All prompts are in Vietnamese, following strict JSON output format.
"""

# ---------------------------------------------------------------------------
#  Prompt 1: Executive Summary (SPEC §5.1)
# ---------------------------------------------------------------------------

EXECUTIVE_SUMMARY_PROMPT = """Bạn là một nhà phân tích thể thao chuyên nghiệp. Dựa trên tổng hợp tin tức thể thao Việt Nam và quốc tế dưới đây, hãy viết một đoạn văn tổng quan (Executive Summary) bằng tiếng Việt.

**Yêu cầu:**
- Độ dài: 200-400 từ
- Phong cách: Chuyên nghiệp, súc tích, khách quan
- Nội dung bao gồm:
  1. Bức tranh chung của lĩnh vực thể thao trong tuần ({date_from} đến {date_to})
  2. Các xu hướng nổi bật nhất (prominent trends)
  3. Những diễn biến quan trọng nhất (most noteworthy developments)
  4. Nhận định tổng thể

**Thống kê:**
- Tổng bài viết: {total_articles}
- Nguồn: {sources}
- Kỳ báo cáo: {date_from} — {date_to}

**Tổng hợp tin tức:**
{article_summaries}

**Output:** Viết duy nhất 1 đoạn văn Executive Summary bằng tiếng Việt."""


# ---------------------------------------------------------------------------
#  Prompt 2: Keyword Extraction (SPEC §5.2)
# ---------------------------------------------------------------------------

KEYWORD_EXTRACTION_PROMPT = """Bạn là chuyên gia phân tích dữ liệu tin tức thể thao. Dựa trên corpus tin tức bên dưới, hãy trích xuất {num_keywords} từ khóa/chủ đề nổi bật nhất.

**Corpus:**
{text_corpus}

**Output format (JSON):**
{{
  "keywords": [
    {{"keyword": "tên từ khóa", "frequency": số_lần_xuất_hiện_ước_tính, "category": "football|basketball|tennis|esports|swimming|athletics|multi-sport|other"}}
  ]
}}

**Quy tắc:**
- Ưu tiên tên riêng (người, giải đấu, đội bóng)
- Frequency là ước tính dựa trên số lần xuất hiện trong corpus
- Category phải thuộc enum: football, basketball, tennis, esports, swimming, athletics, multi-sport, other
- Sắp xếp giảm dần theo frequency
- Trả về ĐÚNG {num_keywords} từ khóa
- Output phải là JSON hợp lệ, KHÔNG kèm markdown code block"""


# ---------------------------------------------------------------------------
#  Prompt 3: Highlighted News (SPEC §5.3)
# ---------------------------------------------------------------------------

HIGHLIGHTED_NEWS_PROMPT = """Bạn là biên tập viên thể thao cấp cao. Dựa trên danh sách bài viết bên dưới, hãy chọn {top_n} bài quan trọng nhất và tóm tắt ngắn gọn.

**Danh sách bài viết:**
{articles}

**Tiêu chí xếp hạng (relevance_score 0-1):**
1. Tầm ảnh hưởng: Bài viết tác động đến nhiều người/cộng đồng (weight: 0.3)
2. Tính thời sự: Sự kiện mới nhất, đang diễn ra (weight: 0.25)
3. Tính độc quyền: Tin độc, góc nhìn mới (weight: 0.2)
4. Tính viral: Khả năng được chia sẻ rộng rãi (weight: 0.15)
5. Chất lượng nội dung: Bài viết chuyên sâu, có phân tích (weight: 0.1)

**Output format (JSON):**
{{
  "highlighted_news": [
    {{
      "title": "tiêu đề gốc của bài viết",
      "summary": "tóm tắt 2-3 câu bằng tiếng Việt",
      "url": "url gốc của bài viết",
      "source": "tên nguồn báo",
      "relevance_score": 0.95
    }}
  ]
}}

**Quy tắc:**
- Sắp xếp giảm dần theo relevance_score
- Title và URL phải CHÍNH XÁC từ danh sách bài viết, KHÔNG được tự bịa
- Summary phải bằng tiếng Việt, 2-3 câu ngắn gọn
- Output phải là JSON hợp lệ, KHÔNG kèm markdown code block"""


# ---------------------------------------------------------------------------
#  Prompt 4: Batch Summary (SPEC §5.4)
# ---------------------------------------------------------------------------

BATCH_SUMMARY_PROMPT = """Tóm tắt các bài viết thể thao sau thành 1 đoạn văn ngắn (100-150 từ), nêu bật các sự kiện chính:

{articles}

**Output:** 1 đoạn văn tóm tắt bằng tiếng Việt. Chỉ viết đoạn văn, không thêm tiêu đề hay ghi chú."""
