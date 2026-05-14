# Phase 2 Edge Cases: RAG Pipeline & Backend Services

This document covers edge cases related to query processing, retrieval, and LLM response generation.

| Edge Case | Description | Mitigation Strategy |
| :--- | :--- | :--- |
| **Mixed Intent Query** | User asks "What is the exit load and should I invest?" (Factual + Advisory). | Intent classifier should flag the advisory part and trigger the refusal guardrail. |
| **Ambiguous Fund Mention** | User asks "What is the expense ratio?" without specifying which of the 5 HDFC funds. | System should ask for clarification or list the ratios for all 5 funds if the query remains ambiguous. |
| **Out-of-Scope Query** | User asks about SBI funds or general stock market advice. | Use a refusal handler to state the system's focus is limited to specific HDFC schemes. |
| **Prompt Injection** | User uses "jailbreak" prompts to try and bypass the "no investment advice" rule. | Robust system prompt and a secondary guardrail LLM to check the final output. |
| **Low Retrieval Confidence** | Similarity score for retrieved chunks is below a safe threshold. | Respond with: "I'm sorry, I couldn't find verified information regarding that specific detail in the official sources." |
| **LLM Verbosity** | LLM generates an accurate answer but exceeds the 3-sentence limit. | Use post-processing logic or a strict system prompt to enforce sentence counts. |
| **PII Camouflage** | User provides PII (like a PAN number) disguised as a question or text. | Use dedicated PII detection libraries (e.g., Presidio) before processing the query. |
| **Hallucination** | LLM makes up a number or fact not present in the retrieved context. | Implement "Grounding" checks; if the answer isn't in the context, refuse to answer. |
