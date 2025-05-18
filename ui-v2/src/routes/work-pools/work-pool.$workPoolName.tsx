import { buildFilterFlowRunsQuery } from "@/api/flow-runs";
import { buildGetWorkPoolQuery } from "@/api/work-pools";
import { buildFilterWorkPoolWorkQueuesQuery } from "@/api/work-queues";
import { WorkPoolDetailsHeader } from "@/components/work-pools/work-pool-details-header";
import { WorkQueueLink } from "@/components/work-pools/work-queue-link";
import { FlowRunsList } from "@/components/flow-runs/flow-runs-list";
import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

const searchParams = z.object({ tab: z.string().optional() }).optional();

export const Route = createFileRoute("/work-pools/work-pool/$workPoolName")({
  validateSearch: zodValidator(searchParams),
  component: RouteComponent,
  loader: async ({ context, params }) => {
    const { workPoolName } = params;
    await context.queryClient.ensureQueryData(buildGetWorkPoolQuery(workPoolName));
    await context.queryClient.ensureQueryData(
      buildFilterWorkPoolWorkQueuesQuery({ work_pool_name: workPoolName })
    );
    await context.queryClient.ensureQueryData(
      buildFilterFlowRunsQuery({
        limit: 20,
        offset: 0,
        sort: "START_TIME_DESC",
        work_pools: { name: [workPoolName] },
      })
    );
  },
  wrapInSuspense: true,
});

function RouteComponent() {
  const { workPoolName } = Route.useParams();
  const search = Route.useSearch();
  const navigate = Route.useNavigate();
  const tab = search?.tab ?? "details";

  const { data: workPool } = useSuspenseQuery(buildGetWorkPoolQuery(workPoolName));
  const { data: queues } = useSuspenseQuery(
    buildFilterWorkPoolWorkQueuesQuery({ work_pool_name: workPoolName })
  );
  const { data: flowRuns } = useSuspenseQuery(
    buildFilterFlowRunsQuery({
      limit: 20,
      offset: 0,
      sort: "START_TIME_DESC",
      work_pools: { name: [workPoolName] },
    })
  );

  return (
    <div className="flex flex-col gap-4">
      <WorkPoolDetailsHeader workPool={workPool} />
      <Tabs
        value={tab}
        onValueChange={(value) =>
          navigate({ to: ".", search: (prev) => ({ ...prev, tab: value }) })
        }
      >
        <TabsList>
          <TabsTrigger value="details">Details</TabsTrigger>
          <TabsTrigger value="runs">Runs</TabsTrigger>
          <TabsTrigger value="queues">Work Queues</TabsTrigger>
        </TabsList>
        <TabsContent value="details">
          <Card className="p-4 space-y-2">
            <div>
              <span className="text-sm text-muted-foreground">Description</span>
              <div>{workPool.description}</div>
            </div>
            <div>
              <span className="text-sm text-muted-foreground">Type</span>
              <div>{workPool.type}</div>
            </div>
          </Card>
        </TabsContent>
        <TabsContent value="runs">
          <FlowRunsList flowRuns={flowRuns} />
        </TabsContent>
        <TabsContent value="queues">
          <ul className="flex flex-col gap-2">
            {queues.map((q) => (
              <li key={q.id}>
                <WorkQueueLink workPoolName={workPoolName} workQueueName={q.name} />
              </li>
            ))}
          </ul>
        </TabsContent>
      </Tabs>
    </div>
  );
}
