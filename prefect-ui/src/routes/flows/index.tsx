import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/flows/')({
  component: FlowList,
})

function FlowList() {
  return (
    <div className="p-2">
      <h3>Flows</h3>
      <ul>
        <li>
          <a href="/flows/flow/1">Flow 1</a>
        </li>
        <li>
          <a href="/flows/flow/2">Flow 2</a>
        </li>
        <li>
          <a href="/flows/flow/3">Flow 3</a>
        </li>
      </ul>
    </div>
  )
}
