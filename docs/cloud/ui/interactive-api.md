# Interactive API


The Interactive API is an embedded GraphQL client that allows you to access all of your data with complete flexibility. Thanks to features like schema introspection and automatic authentication, the interactive API makes it simple to access Cloud. You can also see the GraphQL API documentation directly inline.  

![](/cloud/ui/interactive-api.png)


### Example Query

To find out information about your flows, you could use a flow query.  The basics for that query would be:

```graphql
query {
    flow {
        name
        id
    }
}
```
You can also use the autocomplete to show what other fields you could query:

![](/cloud/ui/dropdown-on-interactive-api.png)

### Nested Query

To get information about the tasks connected to your flows, you could use a nested query:

```graphql
query {
  flow {
    name 
    id
    tasks {
      name
    }
  }
}
```

### Limits and Offset

To limit the number of items that are returned, you can use the Limit selector at the top of the Interactive API page. The default limit is 10 and the maximum is 100. Inline limit arguments are overriden by the value set in the Limit selector. 

To the left of the Limit selector there is also an Offset selector. The Offset selector lets you say where your queries should start. So for example, if your query returned 5 flows and you set the limit to 2 and the offset to 0, you would see the first 2 items returned from your query.  If you set the limit to 2 and the offset to 2, you would see the next 2 items. 

### Query Filters

Another way to limit the results returned would be to filter your search results.  For the flow query example, you could filter the results by looking only for flows with a certain name using the 'where' argument:

```graphql
query {
  flow (where: {name: {_eq: "My Flow Name"}}){
    name 
    id
    tasks {
      name
    }
  }
}
```

We can also filter the results by looking only for flows with tasks with a certain name:

```graphql
query {
  flow (where: {tasks: {name:{_eq: "x"}}})
     {
      name
      id
      tasks {
        name
      }
    }
}
```

And then limit the results further to only show the tasks that have that certain name:

```graphql
query {
  flow (where: {tasks: {name:{_eq: "x"}}})
     {
      name
      id
      tasks (where: {name: {_eq: "x"}}) {
        name
      }
    }
}
```

### Docs

In the docs for the Interactive API (included on the Interactive API page itself) you can find the queries and mutations you can run and see more information about what fields you can request (for queries) or change (for mutations).

![](/cloud/ui/interactive-api-inline-docs.png)  

You can see more about query filters in the [Hasura Docs](https://hasura.io/docs/1.0/graphql/manual/queries/query-filters.html).

You can see more information about GraphQL mutations and queries in the [GraphQL Docs](https://graphql.org/learn/)

Finally, as you read further through the Prefect Cloud docs, look out for the GraphQL header:
### GraphQL <Badge text="GQL"/>

This header shows that we are giving an example of a query or mutation you can run using the Interactive API. 






