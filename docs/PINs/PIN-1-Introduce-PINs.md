---
title: 'PIN-1: Introduce PINs'
sidebarDepth: 0
---

# PIN-1: Introduce Prefect Improvement Notices

Date: 2019-01-23

Author: Jeremiah Lowin

## Status

Proposed

## Context

Prefect is a complex framework for building workflows. As such, changes to its architecture require consideration and input from various stakeholders.

In addition, we desire a way to memorialize _why_ decisions were made. This narrative will allow future contributors to understand not only the way things are (by reading code) but also how they came to be, and the objectives they were designed to meet.

This document is the first **Prefect Improvement Notice**: a proposed change to how Prefect works. Going forward, large architecture decisions can be proposed, debated, and ultimately accepted in this format.

### Why "PIN" and not "ADR"?

"PIN" - Prefect Improvement Notice - follows the example set by Python's PEP. It's quick and easy to say, requiring just one syllable, and while it is a common word, its all-caps variant is not commonly used for anything else in Prefect. It has a nice verb form as well: "PINNED".

"ADR" is an acronym only an engineer could love. It combines three non-harmonious syllables, making it difficult and time-consuming to remember and pronounce: ("Aiy. Dee. Are."). Furthermore, the acronym ADR is already far more widely known as an "American Depository Receipt".

## Decision

We will adopt PINs for proposing, debating, and ultimately accepting or rejecting modifications to Prefect. PINs will be sequentially numbered and not reuse numbers. They will be published as part of Prefect's documentation, providing an architectural narrative of the project's history.

### Format

We will use the following format for PINs:

A PIN is a sequentially-numbered document with a short, imperative title. PINs are written with complete sentences and proper structure. They are conversational documents; reading a series of PINs should emulate the experience of learning _why_ Prefect was built a certain way.

Each PIN has four important sections: Status, Context, Decision, and Consequences.

**Status** is initially "Proposed" and can ultimately become "Accepted" or "Rejected." Future PINs may result in past PINs becoming "Deprecated" or "Superceded."

**Context** gives background for the PIN. It should be complete, including any information relevant to the PIN even if it might lead to its rejection. The goal of this section is to prepare readers so that they fully understand the decision being proposed.

**Decision** discretely explains what the PIN proposes. While the same information may be discussed in the context section (in order to provide arguments for and against), the "decision" is ultimately what is being proposed. It should be presented in an active plural voice ("we will...")

**Consequences** describes the context _after_ adopting the decision. This section should include both positive and negative ramifications.

### Process

A PIN should be submitted to a code repository as a pull request. The PR is an appropriate, archivable forum for discussing the content and nature of the PIN. However, a PIN's proposed decision does NOT have to be accepted in order for its PR to be accepted. We want to include PINs that have not yet been accepted, or that have been rejected. Any discussion / modification to the PR that happens, either in the PR or after the PR is merged, should be reflected in the PIN, if appropriate.

## Consequences

Going forward, large-scale modifications to Prefect will be proposed via PIN.
