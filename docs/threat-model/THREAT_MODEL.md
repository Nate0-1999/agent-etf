# Threat Model

## Main Threats

1. Unauthorized order submission.
2. LLM hallucination producing unsafe strategy updates.
3. Strategy drift between approval and submission.
4. Broker permission mismatch.

## Controls

- 3-step approval with cooldown and hash-locked intent.
- Sequential dissent-based audit councils.
- Approval bundle invalidation on drift.
- Broker permission profile gating.

## Deferred for Post-MVP

- Multi-tenant RBAC.
- Hardware-backed signing.
- Live trading activation controls.
