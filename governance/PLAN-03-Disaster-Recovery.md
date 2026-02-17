# PLAN-03: AI Factory Disaster Recovery & Continuity (DRP)

**Version:** 2026.1.0  
**Classification:** Internal / Sovereign AI Factory  
**Standard Alignment:** NIST SP 800-34  

---

## 1. Risk Assessment
The primary risks to the 6-GPU cluster include:
1. **Hardware Failure:** SSD/Boot drive corruption.
2. **Data Corruption:** Vector database or Model weight corruption.
3. **Configuration Drift:** Inconsistent local environment changes.

## 2. Recovery Time Objective (RTO)
* **Goal:** 4 Hours from total host failure to "Inference Active" state.

## 3. Recovery Strategy (The "Ground Zero" Protocol)
Recovery is automated via the files in the `/infra` directory of this repository:
1. **Base OS:** Re-image with Ubuntu Server (Headless).
2. **IaC Deployment:** Run `terraform apply` to provision the network and VM layers.
3. **Orchestration:** Install MicroK8s and apply the GPU Operator manifest.
4. **Data Restoration:** Pull latest `pgvector` backups from off-site MinIO storage.

## 4. Backup Frequency
* **Configuration:** Real-time via Git (this repo).
* **Databases:** Daily automated snapshots to encrypted S3-compatible storage.
* **Model Weights:** Mirrored locally; verified against SHA-256 hashes upon restoration.
