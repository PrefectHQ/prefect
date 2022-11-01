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

# Collections Catalog

Prefect integrations are organized into collections of pre-built [tasks](/concepts/tasks/), [flows](/concepts/flows/), [blocks](/concepts/blocks/) and more that are installable as PyPI packages.

Collections are grouped around the services with which they interact and can be used to quickly build Prefect dataflows for your existing stack. For example, to move data around in S3 you can use the [`prefect-aws`](https://github.com/PrefectHQ/prefect-aws) collection, or if you want to be notified via Slack as your dataflow runs you can use the [`prefect-slack`](https://github.com/PrefectHQ/prefect-slack) collection. 

By using Prefect Collections, you can eliminate boilerplate code that you need to write to interact with common services, and focus on the outcomes that are important to you.

Below you can find a list of all available Prefect Collections.

<!-- The code below is a jinja2 template that will be rendered by generate_catalog.py -->
<div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(165px, 1fr));">
{% for collection in collections %}
    <div style="padding: 1rem; box-shadow: 0 1px 2px rgba(0, 0, 0, .3); border-radius: 3px">
        <center>
            <div>
                <a href="{{ collection['documentation'] }}">
                    <p style="font-size: 0.8rem">
                        {{collection['tag']}}
                    </p>
                </a>
                <a href="{{ collection['documentation'] }}">
                    <img src={{collection['iconUrl']}} style="max-height: 82px; max-width: 82px">
                </a>
                <p style="font-size: 0.5rem">
                    Maintained by <a href="{{ collection["authorUrl"] }}"><br>{{ collection["author"] }}</a>
                </p>
            </div>
        </center>
    </div>
{% endfor %}
</div >
