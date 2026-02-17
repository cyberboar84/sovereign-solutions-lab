Event ID: AIS-TR-01

Symptom: CoreDNS pods stuck in Pending despite removal of control-plane taint.

Diagnostic: Node reported node.kubernetes.io/not-ready taint.

Root Cause Investigation: Dependency loop where CNI (Cilium) requires a Ready node to schedule, but the node requires a functional CNI to become Ready.

Resolution Path: Verification of Cilium agent logs and kubelet service restart to force CNI configuration discovery.

Incident ID: AIS-TR-04

Symptom: nvidia-device-plugin pod stuck in Terminating state.

Root Cause: Signal mismatch between API Server and containerd following a runtime configuration patch (99-nvidia.toml).

Action: Executed --force --grace-period=0 deletion to clear the stale API object and permit the scheduling of the updated hardware-discovery agent.

Status: Monitoring for successful NVML registration.
