# Sovereign AI Factory (v2.0)

**Enterprise-Grade Inference Infrastructure on Kubernetes**

This repository documents the evolution from a monolithic Docker Compose stack (v1.0) to a distributed **Kubernetes Architecture (v2.0)**. The system transforms a heterogeneous consumer GPU cluster into a tiered, high-availability inference engine using **NVIDIA Triton Inference Server** and **vLLM**.

## 1. Architecture: The Tiered Approach
Unlike v1.0 which forced all cards to act as one giant GPU, v2.0 segments the hardware into logical "Tiers" based on VRAM and Compute capability. This eliminates the "weakest link" bottleneck.

### Hardware Inventory (Verified)
| Tier | Device ID | GPU Model | VRAM | Role |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1** | `GPU-0`, `GPU-5` | **RTX 3080** | 10GB (x2) | **Primary Inference Engine** (Mistral-Nemo). High-bandwidth cards paired for Tensor Parallelism. |
| **Tier 2** | `GPU-2` | **RTX 3060** | 12GB | **Context Worker**. Slower compute, but higher VRAM buffer. Reserved for future Agent/Coder models. |
| **Tier 3** | `GPU-1`, `GPU-3` | **RTX 3060 Ti** | 8GB (x2) | **Utility Pool**. Fast GDDR6 memory but small capacity. Reserved for Embeddings/Vectorization. |
| **Tier 3** | `GPU-4` | **RTX 3070** | 8GB | **Utility Pool**. Additional float throughput for batch processing. |

## 2. Technology Stack (v2.0)
* **Orchestrator:** Kubernetes v1.31 (Bare Metal)
* **Inference Engine:** NVIDIA Triton Server 24.12 (Dec 2024 release)
* **Backend:** vLLM (PagedAttention capable)
* **Storage:** Local HostPath NVMe (`/mnt/sovereign-storage`)
* **Format:** SafeTensors (BF16) - *Legacy GGUF format deprecated*

---

## 3. Operational Playbook

### A. Model Management
We bypass ephemeral container storage by mounting a dedicated host drive.
**Path:** `/mnt/sovereign-storage/models/mistral-nemo/1/`

### B. Deployment Manifests
The cluster uses a custom `RuntimeClass` to expose the NVIDIA drivers to K8s pods.

**Current Deployment:** `triton-stack.yaml`
* **Image:** `nvcr.io/nvidia/tritonserver:24.12-vllm-python-py3`
* **Resources:** Pinned to **Tier 1** via Triton Config.
* **Memory:** 32Gi Shared Memory (SHM) reserved for 32k Context Window.

### C. Engine Tuning
The vLLM engine is manually tuned to fit the 20GB VRAM envelope of Tier 1 while maximizing context.

* **Tensor Parallelism

📄 License MIT License.
