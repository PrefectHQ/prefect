import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/flows/flow/$flowId')({
  component: FlowDetail,
})

function FlowDetail() {

  const { flowId } = Route.useParams()

  return (
    <div className="p-2">
      <h3>Flow {flowId}</h3>
    </div>
  )
}
