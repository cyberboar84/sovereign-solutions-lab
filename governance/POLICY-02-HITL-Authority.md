# POLICY-02: Human-in-the-Loop (HITL) & Agentic Authority

**Version:** 2026.1.0  
**Classification:** Internal / Sovereign AI Factory  
**Standard Alignment:** NIST AI RMF (Govern/Manage)  

---

## 1. Objective
To establish "Policy-Driven Orchestration" that prevents autonomous AI agents from executing high-risk operations without explicit human authorization.

## 2. Risk Tiering
* **Tier 1 (Autonomous):** Read-only queries, summaries, and local log analysis.
* **Tier 2 (Notification):** File modifications within the `scripts/` directory.
* **Tier 3 (Hard Gate):** Destructive actions, firewall changes, or modifications to **SOV-DC-01**.

## 3. Enforcement
All Tier 3 tool calls are intercepted by the **LiteLLM Gateway**. Execution is paused until a manual approval flag is verified in the system logs by the Sovereign Operator.
