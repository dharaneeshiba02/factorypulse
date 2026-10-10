# ADR-002: Shadow Deployment for Model Evaluation

## Status: Accepted

## Context

Promoting a new model to production carries risk.

## Decision

- Production model drives all decisions and alerts
- Staging model scores every request alongside production
- Staging predictions are logged but NEVER acted upon
- Disagreement rate tracked; high disagreement triggers investigation
- Promotion only after shadow period proves equivalent or better

## Consequences

- Double compute cost during shadow period (acceptable for safety-critical)
- Requires careful bookkeeping: shadow predictions must never leak into alerts
