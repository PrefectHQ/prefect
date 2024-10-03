import { createFileRoute } from '@tanstack/react-router'
import { Link } from '@tanstack/react-router'
import { QueryService } from '@/api/service'
import FlowList from '@/components/flows/flows-list'



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
