# ADR 0003 — SEAL over pure prompt engineering

**Status:** Accepted
**Date:** 2026-07-19
**Context:** EVOSEAL needs a mechanism for improving its own capabilities over
time. The fundamental choice is between improving *prompts* (the instructions
given to a fixed model) or improving the *model itself* (via fine-tuning). SEAL
(Self-Adapting Language Models) provides the latter.

---

## 1. Context

There are two broad approaches to making a language-model-based agent improve
over time:

1. **Prompt engineering** — refine the instructions, examples, and context
   provided to a fixed model. No model weights change.
2. **Model adaptation** — fine-tune the model's weights on data produced by the
   evolution loop, so the model itself becomes better at the task.

EVOSEAL originally used only prompt engineering (via DGM's prompt templates). As
the system matured, it adopted SEAL to also support weight-level adaptation.

## 2. Decision

Use **SEAL (Self-Adapting Language Models)** as the model adaptation layer,
alongside (not replacing) prompt-level improvements.

## 3. Rationale

### What SEAL provides that prompt engineering cannot

| Capability | Prompt engineering | SEAL (fine-tuning) |
|-----------|-------------------|-------------------|
| Incorporate new knowledge | Limited to context window | Persists in model weights |
| Few-shot adaptation | Works, but bounded by examples | Learns generalized patterns |
| Self-modification capability | Changes instructions | Changes the model that interprets instructions |
| Token efficiency | Prompts grow with examples | Learned behavior is "free" at inference time |

### Why both, not one or the other

EVOSEAL now supports **two co-evolution paths** that reflect this duality:

1. **Prompt-level co-evolution (CPU-friendly, default)** — a coder model writes
   code, a reviewer critiques it, and the feedback evolves the coder's *system
   prompt*. No GPU required. This is pure prompt engineering, gated by
   regression checks and rollback.

2. **Weight-level fine-tuning (GPU-only)** — LoRA/QLoRA fine-tuning from
   evolution data. This is the SEAL path. Requires a CUDA GPU.

The prompt-level path was added *because* the weight-level path has practical
barriers (GPU cost, training instability, model-specific tuning). The two paths
are complementary:

- Prompt-level is cheaper, faster, and reversible. Good for rapid iteration.
- Weight-level is deeper, persists knowledge, and doesn't consume context
  tokens. Good for durable improvements.

### Why not pure prompt engineering

Pure prompt engineering hits a ceiling:

- **Context window limits.** As the system accumulates examples and rules, the
  prompt grows until it exceeds the model's context window. Fine-tuning
  compresses this knowledge into weights.
- **No generalization.** Prompt-based examples teach by demonstration;
  fine-tuning teaches by *pattern*, which generalizes to unseen cases.
- **Token cost.** Every inference pays the full prompt cost. Learned behavior
  is free after training.

### Why not fine-tuning only

Fine-tuning has its own limits:

- **Requires GPU.** LoRA/QLoRA needs a CUDA GPU. Many EVOSEAL users run on CPU.
- **Training instability.** Fine-tuning can degrade existing capabilities
  (catastrophic forgetting) or amplify biases.
- **Slower feedback loop.** Training takes minutes to hours; prompt changes take
  seconds.
- **Model-specific.** Fine-tuning is tied to a specific model architecture and
  checkpoint. Prompts are model-agnostic.

## 4. Consequences

- **Positive:** The system can improve at two levels, choosing the right tool
  for the situation. Prompt-level works on any hardware. Weight-level provides
  durable knowledge incorporation.
- **Negative:** Two adaptation paths mean two codepaths to maintain, two kinds
  of versioning, and two rollback mechanisms.
- **Neutral:** The prompt-level path is the default; the weight-level path is
  opt-in for GPU-equipped users.

## 5. References

- [`docs/architecture/local_coevolution.md`](../architecture/local_coevolution.md) — prompt-level co-evolution design.
- [`evoseal/fine_tuning/`](../../evoseal/fine_tuning/) — weight-level fine-tuning code.
- [`evoseal/prompt_evolution/`](../../evoseal/prompt_evolution/) — prompt-level co-evolution code.
- [`docs/examples/self_improvement_walkthrough.md`](../examples/self_improvement_walkthrough.md) — concrete before/after example.
