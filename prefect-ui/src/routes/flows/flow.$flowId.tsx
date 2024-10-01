import { createFileRoute } from '@tanstack/react-router'
import { QueryService } from '@/api/service'
import { components } from '@/api/prefect'
import { z } from "zod";

const searchParams = z.object({
  'runs.page': z.number().int().positive().default(1),
  'runs.limit': z.number().int().positive().max(100).default(10),
  'runs.sort': z.enum(['CREATED_DESC', 'CREATED_ASC', 'START_TIME_DESC', 'START_TIME_ASC']).default('CREATED_DESC'),
  'runs.flowRuns.nameLike': z.string().optional(),
  'runs.flowRuns.state.name': z.string().optional(),
  'deployments.page': z.number().int().positive().default(1),
  'deployments.limit': z.number().int().positive().default(10),
}).default({});


const queryParams = (id: string, search: SearchParams) => ({
  queryKey: ['flows', id],
  queryFn: () => Promise.all([
    QueryService.GET('/flows/{id}', { params: { path: { id } } }),
    QueryService.POST('/flow_runs/filter', { body: { flows: { operator: 'and_', id : {any_: [id]} }, offset: search?.['runs.page'] * search?.['runs.limit'], limit: search?.['runs.limit'], sort: 'START_TIME_DESC' } }),
    QueryService.POST('/flow_runs/count', { body: { flows: { operator: 'and_', id : {any_: [id]} } }}),
    QueryService.POST('/deployments/filter', { body: { flows: { operator: 'and_', id : {any_: [id]} }, offset: search['deployments.page'] * search['deployments.limit'], limit: search['deployments.limit'], sort: 'CREATED_DESC' } }),
    QueryService.POST('/deployments/count', { body: { flows: { operator: 'and_', id : {any_: [id]} } }}),
  ]),
  staleTime: 1000 // Data will be considered stale after 1 second.
})

export type SearchParams = z.infer<typeof searchParams>;


export const Route = createFileRoute('/flows/flow/$flowId')({
  component: () => { 
    const [flow, flowRuns, flowRunsCount, deployments, deploymentsCount] = Route.useLoaderData(); 
    return <FlowDetail 
              flow={flow?.data} 
              flowRuns={flowRuns?.data}
              flowRunsCount={flowRunsCount?.data}
              deployments={deployments?.data}
              deploymentsCount={deploymentsCount?.data}
              /> 
  },
  loaderDeps: ({ search }) => search, 
  loader: async ({ deps: search, params: { flowId }, context }) => await context.queryClient.ensureQueryData(queryParams(flowId, search)),
  validateSearch: (search: Record<string, unknown>): SearchParams => searchParams.parse(search),
  wrapInSuspense: true,
})

function FlowDetail({
  flow, 
  flowRuns,
  flowRunsCount,
  deployments,
  deploymentsCount,
}: {
  flow: components['schemas']['Flow'] | undefined,
  flowRuns: components['schemas']['FlowRun'][] | undefined,
  flowRunsCount: number | undefined,
  deployments: components['schemas']['DeploymentResponse'][] | undefined,
  deploymentsCount: number | undefined,
}) {

  return (
    <div className="p-2">
      <h3>Flow</h3>
      { JSON.stringify(flowRuns) }
    </div>
  )
}
