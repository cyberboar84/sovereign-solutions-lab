Standard: GPU Resource Advertising & Discovery

Control ID: AIS-HW-01

Objective: Ensure the Kubernetes scheduler can accurately account for multi-GPU physical resources.

Implementation: > * Plugin: NVIDIA K8s Device Plugin (v0.16.2).

Hardware: 6-GPU Cluster (NVIDIA).

Verification: Execution of kubectl describe node confirming nvidia.com/gpu capacity matches physical hardware inventory.

Constraint: Only pods with explicit limits.nvidia.com/gpu will be permitted access to prevent VRAM over-subscription.
