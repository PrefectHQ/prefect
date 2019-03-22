---
# sidebarDepth: 0
title: Introduction
---


<div align="center" style="margin-bottom:40px;">
<img src="/assets/wordmark-color-horizontal.svg"  width=600 >
</div>


# Welcome to Prefect!

Prefect is a new kind of workflow management system. We started with a simple premise:

> Your code probably works. But sometimes it doesn't.

When your code works, you don't really need a workflow system. We call that  [**positive engineering**](https://medium.com/the-prefect-blog/positive-and-negative-data-engineering-a02cb497583d). It's only when things go wrong that a system like Prefect starts to be valuable. That's **negative engineering**: all the little details that guarantee your code either achieves its goal, or [fails successfully](https://www.youtube.com/watch?v=TlawR_gi8-Y). In this way, workflow systems are actually risk management tools, like insurance: there when you need them, invisible when you don't.

And yet, we don't see a single tool designed that way. Other workflow systems seem to believe that they're actually positive engineering tools, somehow enabling users to do things they couldn't do otherwise. As a result, they feel no shame in asking users to generate yet another config file, or contort code into a convoluted DAG structure. Prefect already knows you can write incredible code; it just wants to make sure it works.

Prefect takes your code and transforms it into a robust, distributed pipeline. You can continue to use your existing tools, languages, infrastructure, and scripts. Prefect is building a rich DAG structure, but in a way that respects positive engineering and doesn't inhibit it. You can use Prefect's functional API to transform scripts with minimal hooks; or you can access the deferred computational graph directly; or any combination thereof. It's up to you.

The most common thing we hear about negative engineering is: **"This should be easy!"**

Prefect is the first step toward making that true.


## The Prefect Platform

Open-sourcing the Prefect Core engine is a major milestone and completes the first stage of the Prefect platform rollout. Soon, we will expand that platform with **Prefect Cloud**. In both its free and paid versions, Prefect Cloud will automatically extend the Core engine with:

- a full GraphQL API
- a complete UI for flows and jobs
- remote execution clusters
- automatic scheduling
- permissions and authorization
- projects for flow organization
- secure runtime secrets and parameters
- ...and a few things we're not ready to talk about yet!

Cloud is already powering Prefect HQ, and we're working with our Lighthouse Partners to get everything ready for a wide release. Please [get in touch](mailto:hello@prefect.io) to apply for access.

We can't wait to see what you build.

Happy engineering!

*- The Prefect Team*
