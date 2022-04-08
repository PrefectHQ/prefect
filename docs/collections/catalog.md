---
description: Check out the pre-built tasks and flows in the Prefect Collections library.
tags:
    - tasks
    - flows
    - collections
    - task library
---

# Prefect Collections Catalog

Below you can find a list of all available Prefect Collections.

<!-- The code below is a jinja2 template that will be rendered by generate_catalog.py -->
<div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(235px, 1fr));">
{% for collection in collections %}
    <div>
        <a href="{{ collection['documentation'] }}">
            <h4>{{collection['collectionName']}}</h4>
        </a>
        <a href="{{ collection['documentation'] }}">
            <img src={{collection['iconUrl']}} style="max-height: 128px; max-width: 128px">
        </a>
        <p style="font-size: 0.6rem">
            Maintained by <a href="{{ collection["authorUrl"] }}">{{ collection["author"] }}</a>
        </p>
    </div>
{% endfor %}
</div >
