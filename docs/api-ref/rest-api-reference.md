---
description: Prefect REST API interactive reference.
tags:
    - REST API
    - Prefect Cloud
hide:
    - toc
title: Prefect Server REST API reference
---

## Prefect Server REST API
The REST API documentation for a locally hosted open-source Prefect server is available below.

<hr>

<div id="redoc-container"></div>
<script src="https://unpkg.com/redoc@2/bundles/redoc.standalone.js"></script>
<script>
    Redoc.init('../schema.json', {
        scrollYOffset: 50,
    }, document.getElementById('redoc-container'))
</script>