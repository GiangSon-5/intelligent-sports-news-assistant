# 🧪 A/B Test Report: summary_style

**Tổng số experiments:** 1

---

## Kết Quả Tổng Hợp

| # | Variant A | Variant B | Score A | Score B | Winner | Margin |
|---|-----------|-----------|---------|---------|--------|--------|
| 1 | summary_concise | summary_detailed | 67.4 | 67.4 | **TIE** | 0.0 |

---

## Thống Kê Thắng/Thua

- **TIE**: 1 lần thắng █

---

## Chi Tiết Output

### Experiment #1 (2026-04-21T21:44:32.191318+07:00)

**Variant A (summary_concise)** — Score: 67.4 | Latency: 34930.38ms
> ERROR: ChatGoogleGenerativeAIError: Error calling model 'gemini-2.5-flash' (RESOURCE_EXHAUSTED): 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, l...

**Variant B (summary_detailed)** — Score: 67.4 | Latency: 35070.81ms
> ERROR: ChatGoogleGenerativeAIError: Error calling model 'gemini-2.5-flash' (RESOURCE_EXHAUSTED): 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, l...

📊 **Verdict:** Hai variants cho kết quả tương đương

---


*Report generated: 2026-04-22T21:21:48.985954+07:00*
