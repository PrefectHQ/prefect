---
description: Prefect REST API interactive reference.
tags:
    - REST API
    - Prefect server
hide:
    - toc
title: Prefect server REST API reference
---

## The Prefect server REST API
The REST API documentation for a locally hosted open-source Prefect server is available below.

<hr>

<div id="redoc-container"></div>
<script src="https://unpkg.com/redoc@2/bundles/redoc.standalone.js"></script>
<script>
    Redoc.init('../schema.json', {
        scrollYOffset: 50,
    }, document.getElementById('redoc-container'))
</script>