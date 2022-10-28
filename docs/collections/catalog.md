---
description: Check out the pre-built tasks and flows in the Prefect Collections library.
tags:
    - tasks
    - flows
    - blocks
    - collections
    - task library
    - integrations
{% for tag in tags %}
    - {{tag}}
{% endfor %}
---

# Prefect Collections Catalog

Below you can find a list of all available Prefect Collections.

<!-- The code below is a jinja2 template that will be rendered by generate_catalog.py -->
<div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(144px, 1fr));">
{% for collection in collections %}
    <div style="padding: 1rem; box-shadow: 0 1px 2px rgba(0, 0, 0, .3); border-radius: 3px">
        <center>
            <div>
                <a href="{{ collection['documentation'] }}">
                    <p style="font-size: 0.7rem">
                        {{collection['tag']}}
                    </p>
                </a>
                <a href="{{ collection['documentation'] }}">
                    <img src={{collection['iconUrl']}} style="max-height: 64px; max-width: 64px">
                </a>
                <p style="font-size: 0.5rem">
                    Maintained by <a href="{{ collection["authorUrl"] }}"><br>{{ collection["author"] }}</a>
                </p>
            </div>
        </center>
    </div>
{% endfor %}
</div >
