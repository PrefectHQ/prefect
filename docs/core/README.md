---
title: Welcome
sidebarDepth: 0
---

<div align="center" style="margin-top:50px; margin-bottom:40px">
    <img src="/img/illustrations/core-illustration.svg"  width=500>
<!-- </div>
<div  style="float:left; width:100%; margin-bottom:40px;"> -->
    <img src="/img/assets/prefect-1.0-logo.png">
</div>

<!-- # Welcome! -->

[Prefect Core](https://www.prefect.io/products/core) is a new kind of workflow management system that makes it easy to take your data pipelines and add semantics like retries, logging, dynamic mapping, caching, failure notifications, and more. 

We started with a simple premise:

> Your code probably works. But sometimes it doesn't.

When your code works as expected, you probably don't even need a workflow system. We call that [**positive engineering**](https://medium.com/the-prefect-blog/positive-and-negative-data-engineering-a02cb497583d) - code that achieves your business objective. It's only when things go wrong that a system like Prefect starts to be valuable. That's [**negative engineering**](https://medium.com/the-prefect-blog/positive-and-negative-data-engineering-a02cb497583d): all the little details that guarantee your code either achieves its goal, or [fails successfully](https://www.youtube.com/watch?v=TlawR_gi8-Y). In this way, workflow systems are actually risk management tools, like insurance: there when you need them, invisible when you don't.

And yet, we don't see a single tool designed that way. Other workflow systems seem to believe that they're actually positive engineering tools, somehow enabling users to do things they couldn't do otherwise. As a result, they feel no shame in asking users to generate yet another config file, or contort code into a convoluted DAG structure. Prefect already knows you can write incredible code; it just wants to make sure it works.

Prefect takes your code and transforms it into a robust, distributed pipeline. You can continue to use your existing tools, languages, infrastructure, and scripts. Prefect builds a rich DAG structure, but in a way that respects positive engineering and doesn't inhibit it. You can use Prefect's functional API to transform scripts with minimal hooks; or you can access the deferred computational graph directly; or any combination thereof. It's up to you.

The most common thing we hear about negative engineering is: **"This should be easy!"**

Now it can be.

Happy engineering!

_- The Prefect Team_
