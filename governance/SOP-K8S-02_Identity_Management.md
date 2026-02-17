Standard: K8s Workload & Admin Identity

Control ID: AIS-IAM-01

Objective: Ensure all administrative access is bound to the current valid Cluster Certificate Authority (CA).

Incident Resolution: > * Event: TLS X.509 Certificate Mismatch.

Root Cause: Residual admin.conf from a decommissioned cluster instance.

Corrective Action: Rotated local kubeconfig to align with the current v1.31 Root CA.

Security Posture: Enforced file-level permissions (600) on ~/.kube/config to prevent unauthorized credential harvesting.
