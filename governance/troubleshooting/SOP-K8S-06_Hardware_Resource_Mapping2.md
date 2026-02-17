Standard: GPU Resource Discovery

Control ID: AIS-HW-01

Objective: Map physical 6-GPU cluster resources to the Kubernetes scheduler.

Implementation: NVIDIA K8s Device Plugin (v0.16.2).

Technical Verification: kubectl describe node confirm nvidia.com/gpu: 6.

Governance: Only pods with explicit GPU resource limits are permitted to request these devices to ensure deterministic VRAM allocation.
