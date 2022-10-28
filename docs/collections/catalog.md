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

Prefect Collections are groupings of pre-built tasks and flows used to quickly build dataflows with Prefect. 

Collections are grouped around the services with which they interact. For example, to download data from an S3 bucket, you could use the `s3_download` task from the `prefect-aws` collection, or if you want to send a Slack message as part of your flow you could use the `send_message` task from the `prefect-slack` collection. 

By using Prefect Collections, you can reduce the amount of boilerplate code that you need to write for interacting with common services, and focus on outcome you're seeking to achieve.

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
