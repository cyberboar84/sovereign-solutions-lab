# sovereign-infrastructure
# Sovereign AI Factory (v1.0)

A production-grade, air-gapped Generative AI platform engineered to run Llama-3-70B on a heterogeneous consumer GPU cluster. This infrastructure demonstrates "Sovereign AI" principles: total data ownership, local inference, and enterprise identity integration without cloud dependencies.

## 🏗 Architecture Overview

The system orchestrates a **6-GPU split-tensor cluster** (56GB VRAM total) to serve a quantized 70B parameter model with a 16k context window. It integrates a Windows Active Directory Domain Controller for RBAC (Role-Based Access Control) and a persistent Data Layer (Postgres + MinIO) for RAG (Retrieval Augmented Generation).

### **Hardware Layer (The "Frankenstein" Cluster)**
* **Compute:** 6x Mixed NVIDIA GPUs (RTX 3080s, 3070, 3060 Tis, 3060 12GB).
* **Optimization:** Manual `tensor-split` configuration (`14,13,11,11,11,18`) tuned to VRAM capacity per card.
* **Cooling:** Custom Python middleware (`force_fans.py`) ensuring thermal stability under sustained inference loads.

### **Software Stack (Docker Compose)**
| Service | Technology | Role |
| :--- | :--- | :--- |
| **Inference Engine** | `llama.cpp` (Server) | GGUF Model Serving (Meta-Llama-3.1-70B-Instruct) |
| **Orchestration** | Docker Compose | Service mesh, volume management, and networking |
| **Identity** | Windows Server 2022 | Active Directory (LDAP) for centralized authentication |
| **Interface** | Open WebUI | ChatGPT-like frontend with RAG and Document parsing |
| **Data Lake** | MinIO (S3) | Object storage for raw documents (PDFs, Code) |
| **Knowledge DB** | PostgreSQL + pgvector | Vector database for semantic search and chat history |

## 🚀 Key Capabilities

* **70B Parameter Inference:** Running a state-of-the-art model locally by splitting layers across PCIe buses.
* **16k Context Window:** Optimized VRAM allocation allows for analyzing large documents (whitepapers, codebases) in a single prompt.
* **Sovereign RAG:** Documents uploaded to the workspace are vectorized locally; no data ever leaves the network.
* **Enterprise Security:** Users authenticate via `sovereign.lan` Active Directory credentials.
* **Self-Healing:** Systemd orchestration scripts ensure the entire stack (Cooling -> Network -> AD -> AI) boots autonomously after power loss.

## 🛠 Deployment

### **Prerequisites**
* Ubuntu 22.04 LTS with NVIDIA Container Toolkit.
* KVM/Libvirt (for the Windows DC).
* ~60GB System RAM.

### **Configuration**
The cluster uses a configured `compose.yaml` with environment variable injection for secrets.

# Balanced for 3080 (10GB) + 3060 (12GB) + 3060Ti (8GB) mix
--tensor-split 14,13,11,11,11,18

Zone A (Inference): localhost:8000 (No external access).

Zone B (Interface): 0.0.0.0:8080 (Accessible via LAN/VPN).

Zone C (Data): Internal Docker Network (Postgres/MinIO isolated).

📄 License
MIT License.
