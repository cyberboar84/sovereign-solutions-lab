Standard: Secure CLI Tooling Operations

Control ID: AIS-OPS-01

Objective: Prevent tool "blindness" and ensure consistent administrative visibility.

Incident: Cilium CLI failed to connect to the Control Plane via localhost:8080.

Root Cause: Environment variable erasure during sudo elevation.

Corrective Action: Enforce explicit --kubeconfig flags for all out-of-process CLI tools (Cilium, Helm, etc.) to maintain the cluster's secure API endpoint (192.168.1.232:6443).
