
<!-- The code below is a jinja2 template that will be rendered by create_integrations_cards.py -->
<CardGroup cols={4}  className="text-center">

{% for integration in integrations %}
    <Card title="{{ integration['tag'] }}">
        <a href="{{ integration['documentation'] }}"> <img src="{{ integration['iconUrl'] }}" alt="{{ integration['integrationName'] }}"/>
        </a>
        Maintained by <a href="{{ integration['authorUrl'] }}"> {{ integration['author'] }} </a>
    </Card>
{% endfor %}

</CardGroup>
