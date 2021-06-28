# Interactive API


The Interactive API is an embedded GraphQL client that allows you to access all of your data with complete flexibility. Thanks to features like schema introspection and automatic authentication, the interactive API makes it simple to access all metadata. You can also see the GraphQL API documentation directly inline.

![](/orchestration/ui/interactive-api.png)


### Basic Query

Let's start with an example of how you might find basic information about your flows.

```graphql
query {
    flow {
        name
        id
    }
}
```
Notice that when we want to get the `flow` object, we must wrap it in a `query` block. This tells GraphQL that we're _retrieving_ something from the schema, as opposed to a `mutation` block which allows us to manipulate our data.

We've told the server to return a list of `flow` objects, each containing their respective `name` and `id` fields. As you interact with the schema in the editor window, you'll see an autocomplete window that will show hints of other available fields, which you can select to insert into your query. 

![](/orchestration/ui/dropdown-on-interactive-api.png)

You can see more information about GraphQL mutations and queries in the [GraphQL Docs](https://graphql.org/learn/)

### Nested Query

Let's build on our earlier query to get information about the tasks associated with our flows. One way to accomplish this would be to use a nested query:

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
We've nested `tasks` within the `flow` object, which tells the server to retrieve tasks only within the context of each flow that it returns.
### Limits and Offset

To limit the number of items that are returned, you can use the Limit selector at the top of the Interactive API page. The default limit is 10 and the maximum is 100. Inline limit arguments are overriden by the value set in the Limit selector.

To the left of the Limit selector there is also an Offset selector. The Offset selector tells the server at which index your queries should start. For example, if your unlimited query would return 5 flows and you set the limit to 2, an offset of 0 would would return the first two items in the set. To get the next two items with no overlap, you would set the offset to 2.

### Query Filters

Another way to limit the results returned would be to filter your search results. Building on our earlier flow query, we add a `where` argument to look for flows with a certain name:

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
To learn more about the various query filters available (there are many more than the examples above!) head over to the [Hasura Docs](https://hasura.io/docs/1.0/graphql/core/queries/index.html).

### Schema

In the docs for the Interactive API (included on the Interactive API page itself) you can find the schema - information about the queries and mutations you can run and more information about what fields you can request (for queries) or change (for mutations).  The schema also tells what type (String, Object, uuid) each field (and argument) should be.

![](/orchestration/ui/interactive-api-inline-docs.png)

### More Examples

Finally, as you read further through the Prefect docs, look out for the GraphQL badge:

<Badge text="GQL"/>

This shows that we are giving an example of a query or mutation you can run using the Interactive API.
