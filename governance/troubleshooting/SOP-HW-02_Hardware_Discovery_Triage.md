Event: GPU Resource Omission in Node Capacity.

Symptom: NVIDIA Device Plugin reported Running but nvidia.com/gpu count was 0 or null.

Technical Investigation: Verify CNI/CRI mapping between containerd and nvidia-container-runtime.

Control Objective: Ensure exact parity between physical hardware inventory and scheduler availability.
