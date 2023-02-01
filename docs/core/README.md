---
title: Welcome
sidebarDepth: 0
---

<div style="border: 2px solid #27b1ff; border-radius: 10px; padding: 1em;">
Looking for the latest <a href="https://docs.prefect.io/">Prefect 2</a> release? Prefect 2 and <a href="https://app.prefect.cloud">Prefect Cloud 2</a> have been released for General Availability. See <a href="https://docs.prefect.io/">https://docs.prefect.io/</a> for details.
</div>

<div align="center" style="margin-top:50px; margin-bottom:40px">
    <img src="/illustrations/core-illustration.svg"  width=500>
</div>
<div  style="float:left; width:100%; margin-bottom:40px;">
    <img src="/assets/prefect-1.0-logo.png"  width=500 >
</div>

<!-- # Welcome! -->

[Prefect 1](https://www.prefect.io/products/core) is a workflow management system that makes it easy to take your data pipelines and add semantics like retries, logging, dynamic mapping, caching, failure notifications, and more. 

We started with a simple premise:

> Your code probably works. But sometimes it doesn't.

When your code works as expected, you probably don't even need a workflow system. We call that [**positive engineering**](https://medium.com/the-prefect-blog/positive-and-negative-data-engineering-a02cb497583d) - code that achieves your business objective. It's only when things go wrong that a system like Prefect starts to be valuable. That's [**negative engineering**](https://medium.com/the-prefect-blog/positive-and-negative-data-engineering-a02cb497583d): all the little details that guarantee your code either achieves its goal, or [fails successfully](https://www.youtube.com/watch?v=TlawR_gi8-Y). In this way, workflow systems are actually risk management tools, like insurance: there when you need them, invisible when you don't.

And yet, we don't see a single tool designed that way. Other workflow systems seem to believe that they're actually positive engineering tools, somehow enabling users to do things they couldn't do otherwise. As a result, they feel no shame in asking users to generate yet another config file, or contort code into a convoluted DAG structure. Prefect already knows you can write incredible code; it just wants to make sure it works.

Prefect 1 takes your code and transforms it into a robust, distributed pipeline. You can continue to use your existing tools, languages, infrastructure, and scripts. Prefect 1 builds a rich DAG structure, but in a way that respects positive engineering and doesn't inhibit it. You can use Prefect's functional API to transform scripts with minimal hooks; or you can access the deferred computational graph directly; or any combination thereof. It's up to you.

Prefect 2 takes it even further by allowing you to run any code without requiring a DAG structure. For more details on that, check out the [Prefect 2 documentation](https://docs.prefect.io/).

Happy engineering!

_- The Prefect Team_
