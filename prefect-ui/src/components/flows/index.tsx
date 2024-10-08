import { components } from "@/api/prefect";
import DataTable from './data-table'
import { deploymentsCountQueryParams, getLatestFlowRunsQueryParams, getNextFlowRunsQueryParams } from './queries'
import { useMemo } from "react";
import { useQueries } from "@tanstack/react-query";

export default function FlowList({
  flows
}: {
  flows: components['schemas']['Flow'][]
}) {

  const queryParams = useMemo(() => [
    ...flows.map(flow => deploymentsCountQueryParams(flow.id as string, { staleTime: 100 })),
    ...flows.map(flow => getLatestFlowRunsQueryParams(flow.id as string, 60, { staleTime: 100 })),
    ...flows.map(flow => getNextFlowRunsQueryParams(flow.id as string, 60, { staleTime: 100 })),
  ], [flows])

  useQueries({queries: queryParams})


  return (
    <div className="container mx-auto">
      <DataTable flows={flows} />
    </div>
  )
}