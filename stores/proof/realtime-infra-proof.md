# Proof — Realtime Infrastructure

Stack:
- NATS
- Redis Streams
- Temporal
- Postgres

Sonuç:
- 14k concurrent workflow
- <220ms event propagation
- exactly-once workflow recovery

En büyük bottleneck:
workflow state serialization.
