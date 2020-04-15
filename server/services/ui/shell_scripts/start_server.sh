#!/usr/bin/env bash

echo "First echo: $PREFECT_SERVER__GRAPHQL_URL"

if [ $PREFECT_SERVER__GRAPHQL_URL != 'http://localhost:4200/graphql' ]
then
    echo "Second echo: $PREFECT_SERVER__GRAPHQL_URL"
    echo "Replacing graphql references with: $PREFECT_SERVER__GRAPHQL_URL"
    for i in /var/www/js/*.js; do
        echo $i
        echo "s,http://localhost:4200/graphql,$PREFECT_SERVER__GRAPHQL_URL,g"
        sed -i -e "s,http://localhost:4200/graphql,$PREFECT_SERVER__GRAPHQL_URL,g" $i
    done
fi

echo "👾👾👾 UI running at localhost:8080 👾👾👾"

nginx -g "daemon off;"