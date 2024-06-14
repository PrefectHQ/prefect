
<!-- The code below is a jinja2 template that will be rendered by create_integrations_cards.py -->
<CardGroup cols={4}  className="text-center">

{% for integration in integrations %}
    <Card title="{{ integration['tag'] }}">
        [![{{ integration['integrationName'] }}]({{ integration['iconURL'] }})] {{ integration['documentation'] }})
        [Maintained by ]( {{ integration['authorUrl'] }} )
    </Card>
{% endfor %}

</CardGroup>
