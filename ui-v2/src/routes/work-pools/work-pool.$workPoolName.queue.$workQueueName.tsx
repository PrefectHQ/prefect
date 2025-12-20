import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { Suspense, useCallback, useMemo } from "react";
import { z } from "zod";
import {
	buildWorkPoolQueueDetailsQuery,
	workPoolQueuesQueryKeyFactory,
} from "@/api/work-pool-queues";
import { buildGetWorkPoolQuery } from "@/api/work-pools";
import { CodeBanner } from "@/components/code-banner";
import {
	LayoutWell,
	LayoutWellContent,
	LayoutWellHeader,
} from "@/components/ui/layout-well";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { WorkPoolQueueDetails } from "@/components/work-pools/work-pool-queue-details";
import { WorkPoolQueuePageHeader } from "@/components/work-pools/work-pool-queue-page-header";
import { WorkPoolQueueRunsTab } from "@/components/work-pools/work-pool-queue-runs-tab";
import { WorkPoolQueueUpcomingRunsTab } from "@/components/work-pools/work-pool-queue-upcoming-runs-tab";
import { cn } from "@/utils";

const searchParams = z.object({
	tab: z.enum(["Details", "Upcoming Runs", "Runs"]).default("Upcoming Runs"),
});

type SearchParams = z.infer<typeof searchParams>;

export const Route = createFileRoute(
	"/work-pools/work-pool/$workPoolName/queue/$workQueueName",
)({
	validateSearch: zodValidator(searchParams),
	component: RouteComponent,
	loader: async ({ params, context: { queryClient } }) => {
		// Critical data - must await
		const queue = await queryClient.ensureQueryData(
			buildWorkPoolQueueDetailsQuery(params.workPoolName, params.workQueueName),
		);

		// Prefetch work pool data for better UX
		void queryClient.prefetchQuery(buildGetWorkPoolQuery(params.workPoolName));

		return { queue };
	},
	wrapInSuspense: true,
});

function RouteComponent() {
	const { workPoolName, workQueueName } = Route.useParams();
	const { tab } = Route.useSearch();
	const navigate = useNavigate({ from: Route.fullPath });
	const queryClient = useQueryClient();

	const { data: queue } = useSuspenseQuery(
		buildWorkPoolQueueDetailsQuery(workPoolName, workQueueName),
	);

	const { data: workPool } = useSuspenseQuery(
		buildGetWorkPoolQuery(workPoolName),
	);

	// Determine CLI command based on work pool type
	const isAgentPool = workPool.type === "prefect-agent";
	const codeBannerCommand = isAgentPool
		? `prefect agent start --pool "${workPool.name}" --work-queue "${queue.name}"`
		: `prefect worker start --pool "${workPool.name}"`;

	const tabs = useMemo(
		() => [
			{
				id: "Details",
				label: "Details",
				hiddenOnDesktop: true, // Hide on xl screens and above
			},
			{
				id: "Upcoming Runs",
				label: "Upcoming Runs",
				hiddenOnDesktop: false,
			},
			{
				id: "Runs",
				label: "Runs",
				hiddenOnDesktop: false,
			},
		],
		[],
	);

	const handleTabChange = useCallback(
		(newTab: string) => {
			void navigate({
				search: { tab: newTab as SearchParams["tab"] },
			});
		},
		[navigate],
	);

	const handleQueueUpdate = useCallback(() => {
		// Refresh queue data
		void queryClient.invalidateQueries({
			queryKey: workPoolQueuesQueryKeyFactory.detail(
				workPoolName,
				workQueueName,
			),
		});
	}, [queryClient, workPoolName, workQueueName]);

	return (
		<LayoutWell>
			<LayoutWellContent>
				<LayoutWellHeader>
					<WorkPoolQueuePageHeader
						workPoolName={workPoolName}
						queue={queue}
						onUpdate={handleQueueUpdate}
					/>
					<div className="w-full bg-muted/50 py-6 px-4 rounded-lg mb-6">
						<div className="max-w-4xl mx-auto">
							<CodeBanner
								command={codeBannerCommand}
								title="Start processing work from this queue"
								subtitle="Run this command to start."
								className="py-0"
							/>
						</div>
					</div>
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
									<WorkPoolQueueDetails
										workPoolName={workPoolName}
										queue={queue}
									/>
								</Suspense>
							</TabsContent>

							<TabsContent value="Upcoming Runs" className="space-y-0">
								<Suspense
									fallback={
										<div className="flex flex-col gap-2">
											<Skeleton className="h-24 w-full" />
											<Skeleton className="h-24 w-full" />
											<Skeleton className="h-24 w-full" />
										</div>
									}
								>
									<WorkPoolQueueUpcomingRunsTab
										workPoolName={workPoolName}
										queue={queue}
									/>
								</Suspense>
							</TabsContent>

							<TabsContent value="Runs" className="space-y-0">
								<Suspense
									fallback={
										<div className="flex flex-col gap-4">
											{/* Search and Filter Controls skeleton */}
											<div className="flex flex-col sm:flex-row gap-4">
												<div className="flex-1">
													<Skeleton className="h-9 w-full" />
												</div>
												<div className="w-full sm:w-64">
													<Skeleton className="h-9 w-full" />
												</div>
											</div>
											{/* Flow runs list skeleton */}
											<div className="flex flex-col gap-2">
												<Skeleton className="h-24 w-full" />
												<Skeleton className="h-24 w-full" />
												<Skeleton className="h-24 w-full" />
											</div>
										</div>
									}
								>
									<WorkPoolQueueRunsTab
										workPoolName={workPoolName}
										queue={queue}
									/>
								</Suspense>
							</TabsContent>
						</Tabs>
					</div>

					<aside className="w-full xl:w-80 xl:shrink-0 hidden xl:block">
						<div className="sticky top-8">
							<WorkPoolQueueDetails
								workPoolName={workPoolName}
								queue={queue}
								alternate
							/>
						</div>
					</aside>
				</div>
			</LayoutWellContent>
		</LayoutWell>
	);
}
