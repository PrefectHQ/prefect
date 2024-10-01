import { createFileRoute } from '@tanstack/react-router'
import { QueryService } from '@/api/service'
import { components } from '@/api/prefect'

const queryParams = (id: string) => ({
  queryKey: ['flows', id],
  queryFn: () => Promise.all([
    QueryService.GET('/flows/{id}', { params: { path: { id } } }),
    QueryService.POST('/flow_runs/filter', { body: { flows: { operator: 'and_', id : {any_: [id]} }, offset: 0, limit: 10, sort: 'START_TIME_DESC' } }),
    QueryService.POST('/flow_runs/count', { body: { flows: { operator: 'and_', id : {any_: [id]} } }}),
    QueryService.POST('/deployments/filter', { body: { flows: { operator: 'and_', id : {any_: [id]} }, offset: 0, limit: 10, sort: 'CREATED_DESC' } }),
    QueryService.POST('/deployments/count', { body: { flows: { operator: 'and_', id : {any_: [id]} } }}),
  ]),
  staleTime: 1000 // Data will be considered stale after 1 second.
})

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
  loader: async ({ params: { flowId }, context }) => await context.queryClient.ensureQueryData(queryParams(flowId)),
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
      { JSON.stringify([flow, flowRuns, flowRunsCount, deployments, deploymentsCount]) }
    </div>
  )
}
