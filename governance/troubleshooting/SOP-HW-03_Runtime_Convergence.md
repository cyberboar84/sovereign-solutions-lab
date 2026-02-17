Incident ID: AIS-TR-07

Symptom: OCI Runtime Error (127) / File Descriptor 11 failure.

Root Cause: Cgroup v2 and Systemd driver mismatch in containerd, preventing the NVIDIA pre-start hook from mapping physical libraries.

Resolution Path: > 1. Clean Slate: Wiped config.toml.

2. Alignment: Enforced SystemdCgroup=true for K8s 1.31 compatibility.

3. Binding: Re-linked nvidia-container-toolkit as the primary runtime handler.

Standard: Aligns with CIS Kubernetes Benchmark 1.31 Section 4 (Worker Node Security).
