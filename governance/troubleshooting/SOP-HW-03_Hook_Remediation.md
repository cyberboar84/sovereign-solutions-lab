Incident ID: AIS-TR-07

Symptom: OCI runtime create failed (exit status 127) / proc/self/fd/11 error.

Root Cause: Broken pipe in the NVIDIA pre-start hook, likely due to a path mismatch between legacy nvidia-container-runtime and the modern nvidia-container-toolkit in the containerd config.

Resolution: Reinstalled toolkit and performed a clean-slate generation of config.toml with SystemdCgroup alignment.

Security Status: RECOVERED.

Incident ID: AIS-TR-07

Diagnostic Result: Identified "naked" binary path in nvidia-container-runtime config and improper mode setting (CDI vs Legacy).

Resolution: > 1. Patched /etc/nvidia-container-runtime/config.toml with absolute paths.

2. Reverted mode from CDI to Legacy to align with the K8s Device Plugin spec.

3. Synchronized containerd main config with SystemdCgroup=true.

Status: Awaiting nvidia.com/gpu: 6 confirmation.
