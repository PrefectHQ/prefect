---
description: Check out the implementation recipes collected in the Prefect Recipes library.
tags:
---

# Prefect Recipes

Below you can find a list of all available Prefect Recipes for Prefect 2.0.

<!-- The code below is a jinja2 template that will be rendered by generate_catalog.py -->
<div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); margin: 0 1em 0 auto">
{% for collection in collections %}
    <div>
        <a href="{{ collection['repo'] }}">
            <h3>{{collection['recipeName']}}</h3>
        </a>
        <p style="font-size: 0.8rem">
            {{ collection["description"] }}
        </p>
        <p>
            {% for icon in collection['iconUrl'] %}
                <img src="{{ icon }}" style="max-height: 48px; max-width: 48px; margin: 0 0.5em 0 auto">
            {% endfor %}
        </p>
        <p>
            Maintained by <a href="{{ collection["authorUrl"] }}">{{ collection["author"] }}</a>
        </p>
    </div>
{% endfor %}
</div >
