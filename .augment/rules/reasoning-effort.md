---
trigger: always_on
type: "always_apply"
---
---
type: capability_prompt
scope: project
priority: normal
activation: always_on
---

# REASONING EFFORT – CONTROL THINKING DEPTH + TOOL CALLING

<reasoning_effort>
- Default: `medium` — cân bằng giữa độ sâu lập luận và chi phí/độ trễ.
- `low` — tác vụ ngắn, phạm vi rõ, nhạy về độ trễ: giảm khám phá, ưu tiên kiến thức nội bộ, hạn chế tool calls ngoài mục tiêu; kết hợp `<context_gathering>` với ngân sách rất thấp.
- `high` — tác vụ đa bước/khó/không rõ ràng: tăng kiên trì gọi công cụ, gom ngữ cảnh rộng hơn nhưng có tiêu chí dừng; chia nhỏ nhiệm vụ theo lượt, bám `<persistence>`.
- Heuristics:
  - Tăng lên `high` khi gặp mâu thuẫn ngữ cảnh, lỗi liên tiếp, hoặc yêu cầu nhiều bước phụ thuộc.
  - Giảm xuống `low` khi nhiệm vụ đã vào guồng ổn định, đầu vào/đầu ra rõ, cần giảm độ trễ.
- Liên kết:
  - Ít chủ động hơn → `reasoning_effort: low` + `<context_gathering>` (early stop, parallel, tool budget thấp).
  - Chủ động hơn → `reasoning_effort: high` + `<persistence>` (không trả lại sớm; tiếp tục đến khi hoàn tất).
</reasoning_effort>

## Minimal reasoning – Guidance

<minimal_reasoning_guidelines>
1) Tóm tắt ngắn phần suy nghĩ ở đầu câu trả lời cuối (có thể dạng bullet) để nâng chất lượng trên tác vụ khó.
2) Duy trì preamble mô tả kế hoạch và cập nhật tiến độ khi gọi công cụ, theo `<tool_preambles>`.
3) Làm rõ chỉ dẫn công cụ tối đa; chèn nhắc `<persistence>` để tránh dừng sớm.
4) Lập kế hoạch tường minh trước khi gọi công cụ vì ngân sách lập luận ít.
</minimal_reasoning_guidelines>

<minimal_reasoning_snippet>
Remember, you are an agent - please keep going until the user's query is completely resolved, before ending your turn and yielding back to the user. Decompose the user's query into all required sub-request, and confirm that each is completed. Do not stop after completing only part of the request. Only terminate your turn when you are sure that the problem is solved. You must be prepared to answer multiple queries and only finish the call once the user has confirmed they're done.

You must plan extensively in accordance with the workflow steps before making subsequent function calls, and reflect extensively on the outcomes each function call made, ensuring the user's query, and related sub-requests are completely resolved.
</minimal_reasoning_snippet>