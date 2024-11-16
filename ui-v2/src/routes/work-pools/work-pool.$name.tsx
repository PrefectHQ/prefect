import { getQueryService } from '@/api/service'
import { useSuspenseQuery } from '@tanstack/react-query'
import { createFileRoute } from '@tanstack/react-router'

const buildWorkPoolQuery = (name: string) => ({
  queryKey: ['work-pool', name],
  queryFn: async () => {
    const response = await getQueryService().GET('/work_pools/{name}', {
      params: {
        path: {
          name
        }
      }
    })
    return response.data
  },
  staleTime: 1000,
})

function WorkPoolRoute() {
  const { name } = Route.useParams()
  const { data: workPool } = useSuspenseQuery(buildWorkPoolQuery(name))

  return JSON.stringify(workPool)
}

export const Route = createFileRoute('/work-pools/work-pool/$name')({
  component: WorkPoolRoute,
  loader: ({ params: { name }, context }) =>
    context.queryClient.ensureQueryData(buildWorkPoolQuery(name)),
  wrapInSuspense: true,
})
