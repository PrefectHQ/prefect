import { buildFilterFlowRunsQuery } from "@/api/flow-runs";
import { buildWorkQueueDetailsQuery } from "@/api/work-queues";
import { WorkQueueDetailsHeader } from "@/components/work-pools/work-queue-details-header";
import { FlowRunsList } from "@/components/flow-runs/flow-runs-list";
import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";

const searchParams = z.object({ tab: z.string().optional() }).optional();

export const Route = createFileRoute(
  "/work-pools/work-pool/$workPoolName/queue/$workQueueName"
)({
  validateSearch: zodValidator(searchParams),
  component: RouteComponent,
  loader: async ({ context, params }) => {
    const { workPoolName, workQueueName } = params;
    await context.queryClient.ensureQueryData(
      buildWorkQueueDetailsQuery(workPoolName, workQueueName)
    );
    await context.queryClient.ensureQueryData(
      buildFilterFlowRunsQuery({
        limit: 20,
        offset: 0,
        sort: "START_TIME_DESC",
        work_pools: { name: [workPoolName] },
        work_pool_queues: { name: [workQueueName] },
      })
    );
  },
  wrapInSuspense: true,
});

function RouteComponent() {
  const { workPoolName, workQueueName } = Route.useParams();
  const search = Route.useSearch();
  const navigate = Route.useNavigate();
  const tab = search?.tab ?? "details";

  const { data: workQueue } = useSuspenseQuery(
    buildWorkQueueDetailsQuery(workPoolName, workQueueName)
  );
  const { data: flowRuns } = useSuspenseQuery(
    buildFilterFlowRunsQuery({
      limit: 20,
      offset: 0,
      sort: "START_TIME_DESC",
      work_pools: { name: [workPoolName] },
      work_pool_queues: { name: [workQueueName] },
    })
  );

  return (
    <div className="flex flex-col gap-4">
      <WorkQueueDetailsHeader workPoolName={workPoolName} workQueue={workQueue} />
      <Tabs
        value={tab}
        onValueChange={(value) =>
          navigate({ to: ".", search: (prev) => ({ ...prev, tab: value }) })
        }
      >
        <TabsList>
          <TabsTrigger value="details">Details</TabsTrigger>
          <TabsTrigger value="runs">Runs</TabsTrigger>
        </TabsList>
        <TabsContent value="details">
          <Card className="p-4 space-y-2">
            <div>
              <span className="text-sm text-muted-foreground">Description</span>
              <div>{workQueue.description}</div>
            </div>
            <div>
              <span className="text-sm text-muted-foreground">Priority</span>
              <div>{workQueue.priority}</div>
            </div>
          </Card>
        </TabsContent>
        <TabsContent value="runs">
          <FlowRunsList flowRuns={flowRuns} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
