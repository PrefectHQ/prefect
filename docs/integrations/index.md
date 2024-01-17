---
description: Check out the pre-built tasks and flows in the Prefect Integrations library.
hide:
  - toc
search:
  boost: 2
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

# Integrations

Prefect integrations are organized into collections of pre-built [tasks](/concepts/tasks/), [flows](/concepts/flows/), [blocks](/concepts/blocks/) and more that are installable as PyPI packages.

<!-- The code below is a jinja2 template that will be rendered by generate_catalog.py -->
<div class="collection-grid">
{% for collection in collections %}
    <div class="collection-item">
        <center>
            <div>
                <a href="{{ collection['documentation'] }}">
                    <p style="font-size: 0.8rem">
                        {{collection['tag']}}
                    </p>
                </a>
                <a href="{{ collection['documentation'] }}">
                    <img src={{collection['iconUrl']}} >
                </a>
                <p style="font-size: 0.5rem">
                    Maintained by <a href="{{ collection["authorUrl"] }}"><br>{{ collection["author"] }}</a>
                </p>
            </div>
        </center>
    </div>
{% endfor %}
</div >
