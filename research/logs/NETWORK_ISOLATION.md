# Sovereign Arena: Layer 4 Zero-Trust Networking

In a Sovereign AI environment, the first line of defense is not the model’s alignment, but the network infrastructure. This lab utilizes **Cilium** and **eBPF** to enforce a "Default Deny" posture for LLM inference workloads.

## The "Arena" Architecture
The `sovereign-arena` namespace is logically and physically isolated from the `sovereign-ai` production namespace. Traffic is only permitted via explicit **CiliumNetworkPolicies (CNP)**.

### Policy Enforcement
We utilize Identity-based security rather than IP-based security. 
* **Egress Control:** The Red Team pod (`llama-attacker`) is restricted to specific FQDNs and internal services.
* **Namespace Isolation:** Prevents lateral movement if a model is compromised via prompt injection.

### Key Manifest: Arena Egress
```yaml
apiVersion: "cilium.io/v2"
kind: CiliumNetworkPolicy
metadata:
  name: "arena-to-gateway-only"
  namespace: "sovereign-arena"
spec:
  endpointSelector:
    matchLabels:
      role: attacker
  egress:
    - toEndpoints:
        - matchLabels:
            "k8s:io.kubernetes.pod.namespace": "sovereign-ai"
      toPorts:
        - ports:
            - port: "4000"
              protocol: TCP
