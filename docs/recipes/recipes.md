---
description: Check out the implementation recipes collected in the Prefect Recipes library.
tags:
---

# Prefect Recipes

[Prefect Recipes](https://github.com/PrefectHQ/prefect-recipes) are common, extensible patterns for setting up Prefect in your execution environment with readymade resources like dockerfiles, Terraform files, GitHub actions, and more.

The following are specific Prefect Recipes for Prefect 2.0. You can find the full repository of Recipes at [https://github.com/PrefectHQ/prefect-recipes](https://github.com/PrefectHQ/prefect-recipes).

### Contributing

We're always looking for new recipe contributions! See the [Prefect Recipes](https://github.com/PrefectHQ/prefect-recipes#contributing--swag-) repository for details on how you can add your Prefect 2.0 recipe, share flow best practices with fellow Prefect users, and earn some swag.

## Recipe catalog

<!-- The code below is a jinja2 template that will be rendered by generate_catalog.py -->
<div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); margin: 1rem auto; padding: 0 1rem 0 1rem auto;">
{% for collection in collections %}
    <div>
        <a href="{{ collection['repo'] }}">
            <h3>{{collection['recipeName']}}</h3>
        </a>
        <div style="height: 110px;">
            <p style="font-size: 0.8rem">
                {{ collection["description"] }}
            </p>
        </div>
        <p style="font-size: 0.6rem">
            Maintained by <a href="{{ collection["authorUrl"] }}">{{ collection["author"] }}</a>
        </p>
        <p style="font-size: 0.6rem">
            This recipe uses:
        </p>
        <p>
            {% for icon in collection['iconUrl'] %}
                <img src="{{ icon }}" style="max-height: 48px; max-width: 48px; margin: 0 0.5em 0 auto;">
            {% endfor %}
        </p>
    </div>
{% endfor %}
</div >
