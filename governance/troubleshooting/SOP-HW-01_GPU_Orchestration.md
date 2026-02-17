Standard: GPU Resource Discovery & Scheduling

Control ID: AIS-HW-01

Objective: Ensure the Kubernetes Control Plane accurately accounts for multi-GPU physical resources.

Implementation: > * Provider: NVIDIA Device Plugin (v0.16.2).

Hardware Inventory: 6x Physical GPUs (Total 56GB VRAM).

Status: Active (DaemonSet nvidia-device-plugin-daemonset).

Governance: Resource limits must be strictly enforced on all AI workloads to prevent cross-pod VRAM contention.

Standard: GPU Resource Discovery & Inventory

Control ID: AIS-HW-01

Objective: Ensure exact mapping of physical GPU resources to the Kubernetes scheduler.

Technical Implementation: NVIDIA Device Plugin (v0.16.2).

Hardware Inventory: 6x Physical GPUs (56GB VRAM).

Verification: Successful advertisement of nvidia.com/gpu: 6 via Node Capacity API.

Resolution: > * CRI Patch: Successfully applied 99-nvidia.toml to containerd.

Discovery Strategy: Explicitly set to nvml to ensure direct access to the 6-GPU PCI-e bus.

Audit Status: PASS. Physical hardware now mapped to Kubernetes scheduler.
