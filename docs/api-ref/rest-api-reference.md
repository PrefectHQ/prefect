---
description: Prefect REST API interactive reference.
tags:
    - REST API
    - Prefect Cloud
hide:
    - navigation
    - toc
---

Both Prefect Cloud and locally hosted Prefect servers expose a REST API that gives you access to many observability, coordination, and account management functions of the platform.

Prefect Cloud REST API documentation is available at <a href="https://app.prefect.cloud/api/docs" target="_blank">https://app.prefect.cloud/api/docs</a>.

The Prefect REST API documentation for locally run open-source Prefect servers is available below.

<hr>

<div id="redoc-container"></div>
<script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"> </script>
<script>
    Redoc.init('../schema.json', {
        scrollYOffset: 50,
    }, document.getElementById('redoc-container'))
</script>
