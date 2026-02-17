# 🧪 Sovereign AI Solutions Lab (v1.0)
**Adversarial Orchestration, Linguistic Governance, and High-Fidelity RAG**

![Sovereign AI Factory Architecture](./assets/architecture_master.png)

This laboratory establishes a **Sovereign AI capability** independent of major cloud providers. It documents the evolution from a monolithic Docker stack to a **Kubernetes-orchestrated (v2.1)** multi-GPU cluster, protected by an adversarial "Red Team" testing layer.

---

## 🛡️ Security & Governance Architecture
To meet federal standards for data integrity and sovereignty, this cluster implements:
* **Workload Identity:** **SPIFFE/SPIRE** for identity-based pod communication, eliminating static secrets.
* **Zero-Trust Networking:** **Cilium eBPF-based** micro-segmentation and identity-aware policies. 
* **Immutable Audit:** **Delta Lake** on **MinIO** providing ACID-compliant lineage for every inference event.
* **Linguistic Guardrails:** Post-inference interceptors in the **Triton Adapter** to mitigate exfiltration (See "Golden Boar" Study).

---

## 🔵 Blue Team: The Inference Factory
A heterogeneous 6-GPU local cluster (~56GB VRAM) segmented into logical "Tiers" to optimize for 70B+ model density.

| Tier | Role | Hardware | Purpose |
| :--- | :--- | :--- | :--- |
| **Tier 1** | **Primary Engine** | 2x RTX 3080 | Tensor Parallelism (Mistral-Nemo/70B Models) |
| **Tier 2** | **Context Worker** | RTX 3060 (12GB) | High VRAM buffer for long-context Agent tasks |
| **Tier 3** | **Utility Pool** | 2x 3060 Ti / 3070 | Embeddings, Vectorization, and Batching |

---

## 🔴 Red Team: The Kill Box
A dedicated, network-segmented environment designed to probe the Blue Team infrastructure for vulnerabilities.
* **Arsenal:** **Garak** (LLM Scanners), **PyRIT** (Adversarial Framework), and **Promptfoo** (Regression Testing).
* **Focus:** Mitigating prompt injection, model hallucinations, and "Linguistic Smuggling" (SOV-2026-001).

---

## 🚀 Flagship Project: Gatsby Linguistic Audit
Demonstrates a multi-stage pipeline across the 6-GPU cluster for high-stakes literary analysis.
* **Architecture:** Triple-lineage validation using **DeepSeek-R1 (70B)**, **Tower-Plus (72B)**, and **Llama 3.3 (70B)**.
* **Performance:** Achieved **0.9489 RTSF** (Round-Trip Semantic Fidelity) on Mandarin scholarly translations.

---

## 📂 Repository Roadmap
* **governance/**: Federal-grade GRC artifacts (Disaster Recovery, HITL, Identity Management).
* **governance/troubleshooting/**: Deep-tier logs for GPU orchestration and Cgroup convergence.
* **research/logs/**: Adversarial case studies (e.g., The "Golden Boar" Linguistic Smuggling audit).
* **solutions/gatsby-audit/**: Sanitzed production scripts and flagship deliverables.

---

## 🛠️ Execution & Environment
To maintain environment parity, all scripts are portable.
1. **Secrets:** Set your API gateway key via environment variable: `export SOVEREIGN_API_KEY="your_key"`
2. **Paths:** All scripts use relative paths. Set the working directory to `solutions/gatsby-audit/`.

