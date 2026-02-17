Incident ID: AIS-TR-06

Symptom: NVIDIA Plugin CrashLoopBackOff with empty logs.

Root Cause: Cgroup v2 driver mismatch between containerd and the Linux kernel during GPU resource isolation.

Resolution: Forced SystemdCgroup=true in config.toml and upgraded plugin manifest to v0.17.1 for K8s 1.31 compatibility.

Standard: Aligns with CIS Kubernetes Benchmark 1.31 for secure node configuration.
