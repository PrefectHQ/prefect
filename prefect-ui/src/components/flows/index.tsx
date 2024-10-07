import { components } from "@/api/prefect";
import DataTable from './data-table'
import { deploymentsCountQueryParams, getLatestFlowRunsQueryParams, getNextFlowRunsQueryParams } from './queries'
import { useMemo } from "react";
import { useQueries } from "@tanstack/react-query";

export default function FlowList({
  flows
}: {
  flows: (Omit<components['schemas']['Flow'], 'id'> & Required<Pick<components['schemas']['Flow'], 'id'>>)[] 
}) {

  const queryParams = useMemo(() => [
    ...flows?.map(flow => deploymentsCountQueryParams(flow.id, { staleTime: 100 })),
    ...flows?.map(flow => getLatestFlowRunsQueryParams(flow.id, 60, { staleTime: 100 })),
    ...flows?.map(flow => getNextFlowRunsQueryParams(flow.id, 60, { staleTime: 100 })),
  ], [flows])

  useQueries({queries: queryParams})

  return <DataTable flows={flows} />
}
