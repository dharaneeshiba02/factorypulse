# ADR 0002: Use LangGraph and Qdrant for the maintenance copilot

- **Status:** Accepted
- **Date:** 2026-10-10
- **Decision owners:** FactoryPulse engineering team

## Context

Technicians need diagnostic responses that combine live machine state with
equipment manuals, fault references, and maintenance history. Responses must
show their supporting sources, handle tool failures clearly, and keep work
orders under human control.

## Decision

Use a LangGraph workflow to coordinate a bounded set of read-only machine and
document search tools. Store document chunks and metadata in Qdrant. Retrieve
manual evidence before drafting, preserve source identifiers for citations, and
run a groundedness check before returning a response. Work-order approval stays
with an authorized person.

Treat user-provided text and retrieved documents as untrusted content. Expose
only explicitly allowed tools to the agent, limit tool-call loops, and record
approval actions in the application audit log.

## Alternatives considered

- **A single prompt with direct vector search:** smaller initial implementation,
  but offers less control over tool sequencing, error recovery, and approval
  boundaries.
- **A general-purpose autonomous agent:** flexible, but makes tool use,
  citations, and safety behavior harder to constrain and audit.
- **A hosted-only retrieval service:** can reduce operational work, but adds an
  external dependency and is less suitable for local development.

## Consequences

- Machine context and retrieved source chunks can be passed through a typed,
  inspectable workflow.
- Qdrant must be populated with versioned source metadata and maintained as
  documents change.
- Retrieval quality and claim support need a curated evaluation set.
- Groundedness checks reduce unsupported claims but do not replace technician
  judgment.
- Copilot work orders remain drafts until an authorized user approves them.
