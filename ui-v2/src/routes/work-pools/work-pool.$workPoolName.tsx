import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import type {
  ColumnFiltersState,
  PaginationState,
  SortingState,
} from "@tanstack/react-table";
import { zodValidator } from "@tanstack/zod-adapter";
import { useCallback, useMemo, useState } from "react";
import { z } from "zod";
import { buildFilterDeploymentsQuery } from "@/api/deployments";
import { buildFilterFlowRunsQuery } from "@/api/flow-runs";
import { buildListWorkPoolQueuesQuery } from "@/api/work-pool-queues";
import { buildWorkPoolByNameQuery } from "@/api/work-pools";
import {
  buildListWorkPoolWorkersQuery,
  queryKeyFactory as workPoolsQueryKeyFactory,
} from "@/api/work-pools/work-pools";
import { CodeBanner } from "@/components/code-banner";
import {
  LayoutWell,
  LayoutWellContent,
  LayoutWellHeader,
} from "@/components/ui/layout-well";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { WorkPoolDeploymentsTab } from "@/components/work-pools/work-pool-deployments-tab";
import { WorkPoolDetails } from "@/components/work-pools/work-pool-details";
import { WorkPoolFlowRunsTab } from "@/components/work-pools/work-pool-flow-runs-tab";
import { WorkPoolPageHeader } from "@/components/work-pools/work-pool-page-header";
import { WorkPoolQueuesTable } from "@/components/work-pools/work-pool-queues-table";
import { WorkersTable } from "@/components/work-pools/workers-table";

const workPoolSearchParams = z.object({
  tab: z
    .enum(["Details", "Runs", "Work Queues", "Workers", "Deployments"])
    .default("Runs"),
});

type WorkPoolSearchParams = z.infer<typeof workPoolSearchParams>;

export const Route = createFileRoute("/work-pools/work-pool/$workPoolName")({
  validateSearch: zodValidator(workPoolSearchParams),
  component: RouteComponent,
  loader: async ({ params, context: { queryClient } }) => {
    // Critical data - must await
    const workPool = await queryClient.ensureQueryData(
      buildWorkPoolByNameQuery(params.workPoolName),
    );

    // Prefetch tab data for better UX
    void queryClient.prefetchQuery(
      buildListWorkPoolQueuesQuery(params.workPoolName),
    );
    void queryClient.prefetchQuery(
      buildListWorkPoolWorkersQuery(params.workPoolName),
    );

    // Prefetch filtered data for runs and deployments
    void queryClient.prefetchQuery(
      buildFilterFlowRunsQuery({
        work_pools: {
          operator: "and_",
          name: { any_: [params.workPoolName] },
        },
        limit: 50,
        offset: 0,
        sort: "START_TIME_DESC",
      }),
    );
    void queryClient.prefetchQuery(
      buildFilterDeploymentsQuery({
        offset: 0,
        sort: "CREATED_DESC",
        deployments: {
          operator: "and_",
        },
      }),
    );

    return { workPool };
  },
  wrapInSuspense: true,
});

// Wrapper component for Work Pool Queues tab
const WorkPoolQueuesTabWrapper = ({
  workPoolName,
}: {
  workPoolName: string;
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [sortState, setSortState] = useState<SortingState>([]);

  const { data: queues = [] } = useSuspenseQuery(
    buildListWorkPoolQueuesQuery(workPoolName),
  );

  const filteredQueues = useMemo(() => {
    if (!searchQuery) return queues;
    return queues.filter((queue) =>
      queue.name.toLowerCase().includes(searchQuery.toLowerCase()),
    );
  }, [queues, searchQuery]);

  return (
    <WorkPoolQueuesTable
      queues={filteredQueues}
      searchQuery={searchQuery}
      sortState={sortState}
      totalCount={queues.length}
      workPoolName={workPoolName}
      onSearchChange={setSearchQuery}
      onSortingChange={setSortState}
    />
  );
};

// Wrapper component for Workers tab
const WorkersTabWrapper = ({ workPoolName }: { workPoolName: string }) => {
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  });
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);

  const { data: workers = [] } = useSuspenseQuery(
    buildListWorkPoolWorkersQuery(workPoolName),
  );

  return (
    <WorkersTable
      workPoolName={workPoolName}
      workers={workers}
      pagination={pagination}
      columnFilters={columnFilters}
      onPaginationChange={setPagination}
      onColumnFiltersChange={setColumnFilters}
    />
  );
};

function RouteComponent() {
  const { workPoolName } = Route.useParams();
  const { tab } = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const queryClient = useQueryClient();

  const { data: workPool } = useSuspenseQuery(
    buildWorkPoolByNameQuery(workPoolName),
  );

  const isAgentWorkPool = workPool.type === "prefect-agent";
  const showCodeBanner = workPool.status !== "READY";
  const codeBannerCommand = `prefect ${
    isAgentWorkPool ? "agent" : "worker"
  } start --pool "${workPool.name}"`;

  const tabs = useMemo(
    () =>
      [
        {
          id: "Details",
          label: "Details",
          hidden: false,
          hiddenOnDesktop: true, // Hide on xl screens and above
        },
        {
          id: "Runs",
          label: "Runs",
          hidden: false,
          hiddenOnDesktop: false,
        },
        {
          id: "Work Queues",
          label: "Work Queues",
          hidden: false,
          hiddenOnDesktop: false,
        },
        {
          id: "Workers",
          label: "Workers",
          hidden: isAgentWorkPool,
          hiddenOnDesktop: false,
        },
        {
          id: "Deployments",
          label: "Deployments",
          hidden: false,
          hiddenOnDesktop: false,
        },
      ].filter((tab) => !tab.hidden),
    [isAgentWorkPool],
  );

  const handleTabChange = useCallback(
    (newTab: string) => {
      void navigate({
        search: { tab: newTab as WorkPoolSearchParams["tab"] },
      });
    },
    [navigate],
  );

  const handleWorkPoolUpdate = useCallback(() => {
    // Refresh work pool data
    void queryClient.invalidateQueries({
      queryKey: workPoolsQueryKeyFactory.detailByName(workPoolName),
    });
  }, [queryClient, workPoolName]);

  return (
    <LayoutWell>
      <LayoutWellContent>
        <LayoutWellHeader>
          <WorkPoolPageHeader
            workPool={workPool}
            onUpdate={handleWorkPoolUpdate}
          />
          {showCodeBanner && (
            <div className="w-full flex justify-center">
              <CodeBanner
                command={codeBannerCommand}
                title="Your work pool is almost ready!"
                subtitle="Run this command to start."
                className="py-4 w-2xl"
              />
            </div>
          )}
        </LayoutWellHeader>

        <div className="flex flex-col xl:flex-row xl:gap-8">
          <div className="flex-1">
            <Tabs value={tab} onValueChange={handleTabChange}>
              <TabsList className="grid w-full grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-4">
                {tabs.map((tabItem) => (
                  <TabsTrigger
                    key={tabItem.id}
                    value={tabItem.id}
                    className={tabItem.hiddenOnDesktop ? "xl:hidden" : ""}
                  >
                    {tabItem.label}
                  </TabsTrigger>
                ))}
              </TabsList>

              <TabsContent value="Details" className="space-y-0">
                <WorkPoolDetails workPool={workPool} />
              </TabsContent>

              <TabsContent value="Runs" className="space-y-0">
                <WorkPoolFlowRunsTab workPoolName={workPoolName} />
              </TabsContent>

              <TabsContent value="Work Queues" className="space-y-0">
                <WorkPoolQueuesTabWrapper workPoolName={workPoolName} />
              </TabsContent>

              <TabsContent value="Workers" className="space-y-0">
                <WorkersTabWrapper workPoolName={workPoolName} />
              </TabsContent>

              <TabsContent value="Deployments" className="space-y-0">
                <WorkPoolDeploymentsTab workPoolName={workPoolName} />
              </TabsContent>
            </Tabs>
          </div>

          <aside className="w-full xl:w-80 xl:shrink-0 hidden xl:block">
            <div className="sticky top-8">
              <WorkPoolDetails workPool={workPool} alternate />
            </div>
          </aside>
        </div>
      </LayoutWellContent>
    </LayoutWell>
  );
}
