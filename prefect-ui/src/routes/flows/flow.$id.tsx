import { createFileRoute } from '@tanstack/react-router'
import { QueryService } from '@/api/service'
import { components } from '@/api/prefect'
import { z } from 'zod'
import { zodSearchValidator } from '@tanstack/router-zod-adapter'
import { useMutation, useSuspenseQueries } from '@tanstack/react-query'

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
    'type': z.enum(['span', 'range']).optional(),
    'seconds': z.number().int().positive().optional(),
    'startDateTime': z.date().optional(),
    'endDateTime': z.date().optional(),
    'deployments.page': z.number().int().positive().optional().default(1),
    'deployments.limit': z.number().int().positive().optional().default(10),
  })
  .optional()
  .default({})

const flowQueryParams = (id: string) => ({
  queryKey: ['flows', id],
  queryFn: async () => await QueryService.GET('/flows/{id}', { params: { path: { id } } }),
  staleTime: 1000, // Data will be considered stale after 1 second.
})

const flowRunsQueryParams = (id: string, search: z.infer<typeof searchParams>) => ({
  queryKey: ['flowRun', JSON.stringify({'flowId': id, ...search})],
  queryFn: async () =>
    await QueryService.POST('/flow_runs/filter', {
      body: {
        flows: { operator: 'and_', id: { any_: [id] }, },
        offset: (search?.['runs.page'] - 1) * search?.['runs.limit'],
        limit: search?.['runs.limit'],
        sort: 'START_TIME_DESC',
      },
    }),
  staleTime: 1000, // Data will be considered stale after 1 second.
})

const flowRunsCountQueryParams = (id: string) => ({
  queryKey: ['flowRunCount', JSON.stringify({'flowId': id})],
  queryFn: async () =>
    await QueryService.POST('/flow_runs/count', {
      body: { flows: { operator: 'and_', id: { any_: [id] } } },
    }),
  staleTime: 1000, // Data will be considered stale after 1 second.
})

const deploymentsQueryParams = (id: string, search: z.infer<typeof searchParams>) => ({
  queryKey: ['deployments', JSON.stringify({'flowId': id, ...search})],
  queryFn: async () =>
    await QueryService.POST('/deployments/filter', {
      body: {
        flows: { operator: 'and_', id: { any_: [id] } },
        offset: (search['deployments.page'] - 1) * search['deployments.limit'],
        limit: 10,
        sort: 'CREATED_DESC',
      },
    }),
  staleTime: 1000, // Data will be considered stale after 1 second.
})

const deploymentsCountQueryParams = (id: string) => ({
  queryKey: ['deploymentsCount', JSON.stringify({'flowId': id})],
  queryFn: async () =>
    await QueryService.POST('/deployments/count', {
      body: { flows: { operator: 'and_', id: { any_: [id] } } },
    }),
  staleTime: 1000, // Data will be considered stale after 1 second.
})

export const Route = createFileRoute('/flows/flow/$id')({
  component: () => {
    const { id } = Route.useParams()
    const search = Route.useSearch()
    const query = useSuspenseQueries({'queries': [
        flowQueryParams(id),
        flowRunsQueryParams(id, search),
        flowRunsCountQueryParams(id),
        deploymentsQueryParams(id, search),
        deploymentsCountQueryParams(id),
    ]})
    
    return (
      <FlowDetail
        id = {id}
        flow={query[0].data.data}
        flowRuns={query[1].data.data}
        flowRunsCount={query[2].data.data}
        deployments={query[3].data.data}
        deploymentsCount={query[4].data.data}
      />
    )
  },
  loaderDeps: ({ search }) => search,
  loader: async ({ deps: search, params: { id }, context }) =>
    await Promise.all([
        context.queryClient.ensureQueryData(flowQueryParams(id)),
        context.queryClient.ensureQueryData(flowRunsQueryParams(id, search)).then((data) => {
          data?.data?.map(flowRun => context.queryClient.setQueryData(['flowRun', flowRun.id], flowRun))
          return data
        }),
        context.queryClient.ensureQueryData(flowRunsCountQueryParams(id)),
        context.queryClient.ensureQueryData(deploymentsQueryParams(id, search)).then((data) => {
          data?.data?.map(deployment => context.queryClient.setQueryData(['deployment', deployment.id], deployment))
          return data
        }),
        context.queryClient.ensureQueryData(deploymentsCountQueryParams(id)),
    ]),
  validateSearch: zodSearchValidator(searchParams),
  wrapInSuspense: true,
})

function FlowDetail({
  id,
  flow,
  flowRuns,
  flowRunsCount,
  deployments,
  deploymentsCount,
}: {
  id: string,
  flow: components['schemas']['Flow'] | undefined,
  flowRuns: components['schemas']['FlowRun'][] | undefined,
  flowRunsCount: number | undefined,
  deployments: components['schemas']['DeploymentResponse'][] | undefined,
  deploymentsCount: number | undefined
}) {

  const { mutate: deleteFlow } = useMutation({
    mutationFn: async () => alert(id) //await QueryService.DELETE('/flows/{id}', { params: { path: { id: id } } })
  })

  return (


    <div className="p-2">
      <h3>Flow {flow?.name}</h3>
      <ul>
        Actions
        <li>
          <button
            onClick={() => {
              navigator.clipboard.writeText(flow?.id || '');
              // You might want to add a toast or notification here
            }}
          >
            Copy Id
          </button>
        </li>
        <li><button onClick={() => deleteFlow()}>Delete</button></li>
        <li><a href ={`/automations/create?from=flow&flowId=${flow?.id}`}>Automate</a></li>
      </ul>
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
