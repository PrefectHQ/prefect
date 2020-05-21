const graphqlMocks = [
  '@/graphql/Dashboard/failures.gql',
  '@/graphql/Dashboard/heartbeat.gql',
  '@/graphql/Dashboard/flow-runs.gql',
  '@/graphql/Dashboard/flows.gql',
  '@/graphql/Dashboard/flow-count.gql',
  '@/graphql/Dashboard/upcoming-flow-runs.gql',
  '@/graphql/Dashboard/flow-failures.gql',
  '@/graphql/Dashboard/hello.gql'
]

// Use jest to mock the graphql data
for (let i = 0; i < graphqlMocks.length; ++i) {
  jest.mock(graphqlMocks[i], () => {
    return 'a graphql string'
  })
}

export default {}
