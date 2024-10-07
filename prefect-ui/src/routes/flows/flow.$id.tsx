import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'
import { useSuspenseQueries } from '@tanstack/react-query'
import { FlowQuery } from '@/components/flows/queries'
import FlowDetail from '@/components/flows/detail'


export const searchParams = z
  .object({
    'runs.page': z.number().int().positive().optional().default(1),
    'runs.limit': z.number().int().positive().max(100).optional().default(10),
    'runs.sort': z
      .enum([
        'CREATED_DESC',
        'CREATED_ASC',
        'START_TIME_DESC',
        'START_TIME_ASC',
        'EXPECTED_START_TIME_DESC'
      ])
      .optional()
      .default('CREATED_DESC'),
    'runs.flowRuns.nameLike': z.string().optional(),
    'runs.flowRuns.state.name': z.string().optional(),
    'type': z.enum(['span', 'range']).optional(),
    'seconds': z.number().int().positive().optional(),
    'startDateTime': z.date().optional(),
    'endDateTime': z.date().optional(),
    'deployments.page': z.number().int().positive().optional().default(1),
    'deployments.limit': z.number().int().positive().optional().default(10),
  })
  .optional()
  .default({})

export const Route = createFileRoute('/flows/flow/$id')({
  component: () => {
    const { id } = Route.useParams()
    const flowQuery = new FlowQuery(id)
    const [ 
      { data: flow }, 
      { data: flowRuns },
      { data: flowRunsCount },
      { data: deployments },
      { data: deploymentsCount },
    ] = useSuspenseQueries({'queries': [
      flowQuery.getQueryParams(),
      flowQuery.getFlowRunsQueryParams({'sort': 'START_TIME_DESC', 'offset': 0, 'limit': 10}),
      flowQuery.getFlowRunsCountQueryParams(),
      flowQuery.getDeploymentsQueryParams({'sort': 'CREATED_DESC', 'offset': 0, 'limit': 10}),
      flowQuery.getDeploymentsCountQueryParams(),
    ]})
    
    return (
      <FlowDetail
        flow={flow}
        flowRuns={flowRuns}
        deployments={deployments}
      />
    )
  },
  loaderDeps: ({ search }) => search,
  loader: async ({ params: { id }, context }) => {
    const flow = new FlowQuery(id)
    return await Promise.all([
      context.queryClient.ensureQueryData(flow.getQueryParams()),
      context.queryClient.ensureQueryData(flow.getFlowRunsQueryParams({'sort': 'START_TIME_DESC', 'offset': 0, 'limit': 10})),
      context.queryClient.ensureQueryData(flow.getFlowRunsCountQueryParams()),
      context.queryClient.ensureQueryData(flow.getDeploymentsQueryParams({'sort': 'CREATED_DESC', 'offset': 0, 'limit': 10})),
      context.queryClient.ensureQueryData(flow.getDeploymentsCountQueryParams()),
    ])
  },
  wrapInSuspense: true,
})

