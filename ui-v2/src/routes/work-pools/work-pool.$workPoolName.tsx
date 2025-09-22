import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import type {
	ColumnFiltersState,
	PaginationState,
	SortingState,
} from "@tanstack/react-table";
import { zodValidator } from "@tanstack/zod-adapter";
import { Suspense, useCallback, useMemo, useState } from "react";
import { z } from "zod";
import { buildPaginateDeploymentsQuery } from "@/api/deployments";
import {
	buildCountFlowRunsQuery,
	buildPaginateFlowRunsQuery,
} from "@/api/flow-runs";
import { buildGetFlowRunsTaskRunsCountQuery } from "@/api/task-runs";
import { buildListWorkPoolQueuesQuery } from "@/api/work-pool-queues";
import { buildGetWorkPoolQuery } from "@/api/work-pools";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { WorkPoolDeploymentsTab } from "@/components/work-pools/work-pool-deployments-tab";
import { WorkPoolDetails } from "@/components/work-pools/work-pool-details";
import { WorkPoolFlowRunsTab } from "@/components/work-pools/work-pool-flow-runs-tab";
import { WorkPoolPageHeader } from "@/components/work-pools/work-pool-page-header";
import { WorkPoolQueuesTable } from "@/components/work-pools/work-pool-queues-table";
import { WorkersTable } from "@/components/work-pools/workers-table";
import { cn } from "@/utils";

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
			buildGetWorkPoolQuery(params.workPoolName),
		);

		// Prefetch tab data for better UX
		void queryClient.prefetchQuery(
			buildListWorkPoolQueuesQuery(params.workPoolName),
		);
		void queryClient.prefetchQuery(
			buildListWorkPoolWorkersQuery(params.workPoolName),
		);

		// Prefetch late runs count for each queue (non-blocking)
		void queryClient
			.ensureQueryData(buildListWorkPoolQueuesQuery(params.workPoolName))
			.then((queues) =>
				Promise.all(
					queues.map((queue) =>
						queryClient.prefetchQuery(
							buildCountFlowRunsQuery(
								{
									work_pools: {
										operator: "and_",
										name: { any_: [params.workPoolName] },
									},
									work_pool_queues: {
										operator: "and_",
										name: { any_: [queue.name] },
									},
									flow_runs: {
										operator: "and_",
										state: {
											operator: "and_",
											name: { any_: ["Late"] },
										},
									},
								},
								30000,
							),
						),
					),
				),
			);

		// Prefetch paginated flow runs data
		void queryClient
			.ensureQueryData(
				buildPaginateFlowRunsQuery({
					page: 1,
					limit: 10,
					sort: "START_TIME_DESC",
					work_pools: {
						operator: "and_",
						name: { any_: [params.workPoolName] },
					},
				}),
			)
			.then((paginatedData) =>
				Promise.all(
					(paginatedData.results ?? []).map((flowRun) =>
						queryClient.prefetchQuery(
							buildGetFlowRunsTaskRunsCountQuery([flowRun.id]),
						),
					),
				),
			);

		// Prefetch flow runs count for pagination
		void queryClient.prefetchQuery(
			buildCountFlowRunsQuery({
				work_pools: {
					operator: "and_",
					name: { any_: [params.workPoolName] },
				},
			}),
		);
		void queryClient.prefetchQuery(
			buildPaginateDeploymentsQuery({
				page: 1,
				limit: 50,
				sort: "CREATED_DESC",
				work_pools: {
					operator: "and_",
					name: { any_: [params.workPoolName] },
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

	const { data: queues } = useSuspenseQuery(
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

	const { data: workers } = useSuspenseQuery(
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
		buildGetWorkPoolQuery(workPoolName),
	);

	const showCodeBanner = workPool.status !== "READY";
	const codeBannerCommand = `prefect worker start --pool "${workPool.name}"`;

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
					hiddenOnDesktop: false,
				},
				{
					id: "Deployments",
					label: "Deployments",
					hidden: false,
					hiddenOnDesktop: false,
				},
			].filter((tab) => !tab.hidden),
		[],
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
						<div className="w-full bg-gray-50 py-6 px-4 rounded-lg mb-6">
							<div className="max-w-4xl mx-auto">
								<CodeBanner
									command={codeBannerCommand}
									title="Your work pool is almost ready!"
									subtitle="Run this command to start."
									className="py-0"
								/>
							</div>
						</div>
					)}
				</LayoutWellHeader>

				<div className="flex flex-col xl:flex-row xl:gap-8">
					<div className="flex-1">
						<Tabs value={tab} onValueChange={handleTabChange}>
							<TabsList className="flex w-full overflow-x-auto scrollbar-none">
								{tabs.map((tabItem) => (
									<TabsTrigger
										key={tabItem.id}
										value={tabItem.id}
										className={cn(
											"whitespace-nowrap flex-shrink-0",
											tabItem.hiddenOnDesktop ? "xl:hidden" : "",
										)}
									>
										{tabItem.label}
									</TabsTrigger>
								))}
							</TabsList>

							<TabsContent value="Details" className="space-y-0">
								<Suspense
									fallback={
										<div className="space-y-6">
											<div className="space-y-4">
												<Skeleton className="h-4 w-48" />
												<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
													<div className="space-y-2">
														<Skeleton className="h-3 w-16" />
														<Skeleton className="h-6 w-24" />
													</div>
													<div className="space-y-2">
														<Skeleton className="h-3 w-20" />
														<Skeleton className="h-6 w-32" />
													</div>
													<div className="space-y-2">
														<Skeleton className="h-3 w-24" />
														<Skeleton className="h-6 w-28" />
													</div>
													<div className="space-y-2">
														<Skeleton className="h-3 w-18" />
														<Skeleton className="h-6 w-36" />
													</div>
												</div>
											</div>
											<div className="space-y-3">
												<Skeleton className="h-5 w-40" />
												<div className="space-y-2">
													<Skeleton className="h-32 w-full" />
												</div>
											</div>
										</div>
									}
								>
									<WorkPoolDetails workPool={workPool} />
								</Suspense>
							</TabsContent>

							<TabsContent value="Runs">
								<Suspense
									fallback={
										<div className="flex flex-col gap-2">
											<Skeleton className="h-24 w-full" />
											<Skeleton className="h-24 w-full" />
											<Skeleton className="h-24 w-full" />
										</div>
									}
								>
									<WorkPoolFlowRunsTab workPoolName={workPoolName} />
								</Suspense>
							</TabsContent>

							<TabsContent value="Work Queues" className="space-y-0">
								<Suspense
									fallback={
										<div className="flex flex-col gap-4">
											{/* Toolbar skeleton */}
											<div className="flex items-center justify-between">
												<div className="flex items-center gap-2">
													<Skeleton className="h-6 w-24" />
													<Skeleton className="h-6 w-8" />
												</div>
												<div className="flex items-center gap-2">
													<Skeleton className="h-6 w-64" />
												</div>
											</div>
											{/* Table skeleton */}
											<div className="space-y-2">
												<Skeleton className="h-34 w-full" />
											</div>
										</div>
									}
								>
									<WorkPoolQueuesTabWrapper workPoolName={workPoolName} />
								</Suspense>
							</TabsContent>

							<TabsContent value="Workers" className="space-y-0">
								<Suspense
									fallback={
										<div className="space-y-4">
											{/* Search skeleton */}
											<div className="flex items-center justify-between">
												<Skeleton className="h-4 w-20" />
												<Skeleton className="h-9 w-64" />
											</div>
											{/* Table skeleton */}
											<div className="space-y-2">
												<Skeleton className="h-34 w-full" />
											</div>
										</div>
									}
								>
									<WorkersTabWrapper workPoolName={workPoolName} />
								</Suspense>
							</TabsContent>

							<TabsContent value="Deployments" className="space-y-0">
								<Suspense
									fallback={
										<div className="space-y-4">
											{/* Search skeleton */}
											<div className="flex items-center justify-between">
												<Skeleton className="h-4 w-20" />
												<Skeleton className="h-9 w-64" />
											</div>
											{/* Table skeleton */}
											<div className="space-y-2">
												<Skeleton className="h-34 w-full" />
											</div>
										</div>
									}
								>
									<WorkPoolDeploymentsTab workPoolName={workPoolName} />
								</Suspense>
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
