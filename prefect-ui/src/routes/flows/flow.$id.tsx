import { createFileRoute } from '@tanstack/react-router'
import { QueryService } from '@/api/service'
import { components } from '@/api/prefect'
import { z } from 'zod'
import { zodSearchValidator } from '@tanstack/router-zod-adapter'
import { useSuspenseQuery } from '@tanstack/react-query'

const searchParams = z
  .object({
    'runs.page': z.number().int().positive().optional().default(1),
    'runs.limit': z.number().int().positive().max(100).optional().default(10),
    'runs.sort': z
      .enum([
        'CREATED_DESC',
        'CREATED_ASC',
        'START_TIME_DESC',
        'START_TIME_ASC',
      ])
      .optional()
      .default('CREATED_DESC'),
    'runs.flowRuns.nameLike': z.string().optional(),
    'runs.flowRuns.state.name': z.string().optional(),
    'deployments.page': z.number().int().positive().optional().default(1),
    'deployments.limit': z.number().int().positive().optional().default(10),
  })
  .optional()
  .default({})

const queryParams = (id: string, search:  z.infer<typeof searchParams>) => ({
  queryKey: ['flows', id, JSON.stringify(search)],
  queryFn: () =>
    Promise.all([
      QueryService.GET('/flows/{id}', { params: { path: { id } } }),
      QueryService.POST('/flow_runs/filter', {
        body: {
          flows: { operator: 'and_', id: { any_: [id] } },
          offset: (search?.['runs.page'] - 1) * search?.['runs.limit'],
          limit: search?.['runs.limit'],
          sort: 'START_TIME_DESC',
        },
      }),
      QueryService.POST('/flow_runs/count', {
        body: { flows: { operator: 'and_', id: { any_: [id] } } },
      }),
      QueryService.POST('/deployments/filter', {
        body: {
          flows: { operator: 'and_', id: { any_: [id] } },
          offset:
            (search['deployments.page'] - 1) * search['deployments.limit'],
          limit: 10,
          sort: 'CREATED_DESC',
        },
      }),
      QueryService.POST('/deployments/count', {
        body: { flows: { operator: 'and_', id: { any_: [id] } } },
      }),
    ]),
  staleTime: 1000, // Data will be considered stale after 1 second.
})

export const Route = createFileRoute('/flows/flow/$id')({
  component: () => {
    const { id } = Route.useParams()
    const search = Route.useSearch()
    const { data: [flow, flowRuns, flowRunsCount, deployments, deploymentsCount] } =
      useSuspenseQuery(queryParams(id, search))
    return (
      <FlowDetail
        flow={flow?.data}
        flowRuns={flowRuns?.data}
        flowRunsCount={flowRunsCount?.data}
        deployments={deployments?.data}
        deploymentsCount={deploymentsCount?.data}
      />
    )
  },
  loaderDeps: ({ search }) => search,
  loader: async ({ deps: search, params: { id }, context }) =>
    await context.queryClient.ensureQueryData(queryParams(id, search)),
  validateSearch: zodSearchValidator(searchParams),
  wrapInSuspense: true,
})

function FlowDetail({
  flow,
  flowRuns,
  flowRunsCount,
  deployments,
  deploymentsCount,
}: {
  flow: components['schemas']['Flow'] | undefined
  flowRuns: components['schemas']['FlowRun'][] | undefined
  flowRunsCount: number | undefined
  deployments: components['schemas']['DeploymentResponse'][] | undefined
  deploymentsCount: number | undefined
}) {
  return (
    <div className="p-2">
      <h3>Flow {flow?.name}</h3>
      <ul>
        Flow Runs: {flowRunsCount}
        {flowRuns?.map((flowRun) => <li key={flowRun.id}>{flowRun.name}</li>)}
      </ul>
      <ul>
        Deployments: {deploymentsCount}
        {deployments?.map((deployment) => (
          <li key={deployment.id}>{deployment.name}</li>
        ))}
      </ul>
    </div>
  )
}
