---
description: Prefect REST API interactive reference.
tags:
    - REST API
    - Orion
    - Prefect Cloud
hide:
    - navigation
    - toc
---

# Prefect REST API Reference

This page provides an interactive reference for the Prefect REST API.

For more information about using the REST API, see the [REST API Overview](/api-ref/rest-api/).

<hr>

<div id="redoc-container"></div>
<script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"> </script>
<script>
    Redoc.init('../rest-api/schema.json', {
        scrollYOffset: 50,
    }, document.getElementById('redoc-container'))
</script>