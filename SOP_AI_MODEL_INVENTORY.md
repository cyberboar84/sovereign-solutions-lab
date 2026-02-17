# 📂 SOP: AI Model Inventory & Provenance

This registry tracks model weights, quantization DNA, and architectural origins to ensure data sovereignty and prevent "family bias" during multi-stage validation.

## 1. Production Inference Registry (llama.cpp / GGUF)
*High-density models optimized for the local 6-GPU cluster (~56GB VRAM).*

| Model ID | Base DNA | Quantization | Path (Relative to $MODEL_ROOT) | Research Role |
| :--- | :--- | :--- | :--- | :--- |
| **DeepSeek-R1-70B** | Llama 3 | Q4_K_M | `deepseek-70b/r1-70b.gguf` | Analytical Reasoner |
| **Tower-Plus-72B** | Qwen 2.5 | Q4_K_M | `tower-plus-72b/tower-72b.gguf` | Multilingual Specialist |
| **Llama-3.3-70B** | Llama 3.3 | Q4_K_M | `llama-3.3-70b/llama-3.3.gguf` | Philological Auditor |
| **Tower-13B** | Llama 2 | Q6_K | `tower-13b/tower-13b-v0.1.gguf` | Fast-Path Translation |

## 2. Enterprise Model Archive (Triton / vLLM)
*Unquantized/SafeTensors weights used for high-fidelity verification and RAG.*

| Model ID | Format | Total Size | Role |
| :--- | :--- | :--- | :--- |
| **Mistral-Nemo-HF** | SafeTensors | ~23 GB | Primary vLLM Instance |
| **Tower-13B-ST** | SafeTensors | ~51 GB | High-Fidelity Linguistic Reference |
| **Llama-3 (8B)** | SafeTensors | ~15 GB | Lightweight Utility/Embedding Tasks |

## 3. Maintenance & Governance Procedures

### **A. Hash-Based Verification**
All models must be verified against source SHA-256 hashes before being loaded into the 6-GPU cluster. This prevents "Weight Tampering" during air-gapped or Sovereign transit.

### **B. DNA Isolation (The Triple-Lineage Rule)**
To eliminate "family bias" in high-stakes translations:
* No two models in a validation pipeline shall share a base architecture (e.g., mixing **Llama**, **Qwen**, and **Mistral**).
* This ensured the **0.9489 RTSF score** in the Gatsby Mandarin audit by forcing independent semantic cross-checks.

### **C. Storage Tiering**
* **Hot Storage:** NVMe-backed `~/models` for active inference.
* **Cold Storage:** MinIO-backed `models_archive` for immutable auditing and version control.
