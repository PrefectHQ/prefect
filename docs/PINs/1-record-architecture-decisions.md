---
sidebarDepth: 0
---

# PIN-1: Record architecture decisions

Date: 2019-01-23

## Status

Proposed

## Context

Prefect is a complex framework for building workflows. As such, changes to its architecture require consideration and input from various stakeholders.

In addition, we desire a way to memorialize _why_ decisions were made. This narrative will allow future contributors to understand not only the way things are (by reading code) but also how they came to be, and the objectives they were designed to meet.

This document is PIN 1: a proposed change to how Prefect works. Going forward, large architecture decisions can be proposed, debated, and ultimately accepted in this format.

## Decision

We will adopt PINs for proposing, debating, and ultimately accepting or rejecting modifications to Prefect. PINs will be sequentially numbered and not reuse numbers. They will be published as part of Prefect's documentation, providing an architectural narrative of the project's history.

### Why "PIN" and not "ADR"?

"PIN" - Prefect Improvement Notice - follows the example set by Python's PEP. It's quick and easy to say, requiring just one syllable, and while it is a common word, its all-caps variant is not commonly used for anything else in Prefect. It has a nice verb form as well: "PINNED".

"ADR" is an acronym only an engineer could love. It combines three non-harmonious syllables, making it difficult and time-consuming to remember and pronounce: ("Aiy. Dee. Are."). Furthermore, the acronym ADR is already far more widely known as an "American Depository Receipt".

## Consequences

Going forward, large-scale modifications to Prefect will be proposed via PIN.
