# 1. Record architecture decisions

Date: 2026-06-09
Status: Accepted

## Context

The project is a live demo worked on by both humans and AI agents. Non-obvious
choices (especially around the schema-on-write data layer) get silently undone
when the reasoning isn't written down.

## Decision

We keep lightweight ADRs in `docs/decisions/`, one Markdown file per decision,
numbered sequentially, using this Context / Decision / Consequences template.

## Consequences

- Every meaningful architectural choice has a durable, linkable rationale.
- The barrier to adding one is low (copy this file, fill three sections).
- This file doubles as the template for all future ADRs.
