import { createFileRoute } from '@tanstack/react-router'
import { Link } from '@tanstack/react-router'
import { QueryService } from '@/api/service'



export const Route = createFileRoute('/flows/')({
  component: FlowList,
  loader: async ({ context }) => await context.queryClient.ensureQueryData({
      queryKey: ['flows'],
      queryFn: () => QueryService.POST('/flows/paginate', { body: { page: 1, limit: 10, sort: 'CREATED_DESC' } }).then(
    )
      
    })
  ,
  wrapInSuspense: true,
})

function FlowList() {
  const data = Route.useLoaderData()

  return (
    <div className="p-2">
      <h3>Flows</h3>
      <ul>
        {data?.data?.results?.map((flow: any) => (
          <li key={flow.id}>
            <Link to='/flows/flow/$id' params={{ id: flow.id }}>
              {flow.name}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
