# Triton-OpenAI Adapter: The Linguistic Bridge

Standard inference frontends (Open WebUI, LiteLLM) expect OpenAI-compatible JSON payloads. NVIDIA Triton Inference Server utilizes the KServe/v2 gRPC and HTTP protocols. This adapter acts as the translation layer and a point for security injection.

## Technical Stack
- **Framework:** FastAPI / Uvicorn
- **Backend:** NVIDIA Triton (vLLM Backend)
- **Primary Function:** Maps `v1/chat/completions` to Triton's `/v2/models/{model}/generate` endpoint.

## Security Injection Point
The adapter serves as a "System Prompt Gatekeeper." During research, we utilize this layer to inject environment variables into the model's context for exfiltration testing.

### Logic Flow
1. **Receive:** Standard OpenAI JSON.
2. **Transform:** Extract messages and rebuild the prompt for Mistral-Nemo’s `[INST]` format.
3. **Inject:** Pull `GOLDEN_BOAR` from pod environment variables.
4. **Proxy:** Forward raw tensors to Triton.
