import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { Suspense, useCallback, useMemo } from "react";
import { z } from "zod";
import { categorizeError } from "@/api/error-utils";
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
import { PrefectLoading } from "@/components/ui/loading";
import { RouteErrorState } from "@/components/ui/route-error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { WorkPoolQueueDetails } from "@/components/work-pools/work-pool-queue-details";
import { WorkPoolQueuePageHeader } from "@/components/work-pools/work-pool-queue-page-header";
import { WorkPoolQueueRunsTab } from "@/components/work-pools/work-pool-queue-runs-tab";
import { WorkPoolQueueUpcomingRunsTab } from "@/components/work-pools/work-pool-queue-upcoming-runs-tab";
import { cn } from "@/utils";

const searchParams = z.object({
	queueTab: z
		.enum(["Details", "Upcoming Runs", "Runs"])
		.default("Upcoming Runs"),
});

type SearchParams = z.infer<typeof searchParams>;

export const Route = createFileRoute(
	"/work-pools/work-pool_/$workPoolName/queue/$workQueueName",
)({
	validateSearch: zodValidator(searchParams),
	component: function RouteComponent() {
		function RunsTabSkeleton() {
			return (
				<div className="flex flex-col gap-4">
					<div className="flex flex-col sm:flex-row gap-4">
						<div className="flex-1">
							<Skeleton className="h-9 w-full" />
						</div>
						<div className="w-full sm:w-64">
							<Skeleton className="h-9 w-full" />
						</div>
					</div>
					<div className="flex flex-col gap-2">
						<Skeleton className="h-24 w-full" />
						<Skeleton className="h-24 w-full" />
						<Skeleton className="h-24 w-full" />
					</div>
				</div>
			);
		}

		function UpcomingRunsTabSkeleton() {
			return (
				<div className="flex flex-col gap-2">
					<Skeleton className="h-24 w-full" />
					<Skeleton className="h-24 w-full" />
					<Skeleton className="h-24 w-full" />
				</div>
			);
		}

		function DetailsTabSkeleton() {
			return (
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
			);
		}

		const { workPoolName, workQueueName } = Route.useParams();
		const { queueTab } = Route.useSearch();
		const navigate = Route.useNavigate();
		const queryClient = useQueryClient();

		const { data: queue } = useSuspenseQuery(
			buildWorkPoolQueueDetailsQuery(workPoolName, workQueueName),
		);

		const { data: workPool } = useSuspenseQuery(
			buildGetWorkPoolQuery(workPoolName),
		);

		const isAgentWorkPool = workPool.type === "prefect-agent";
		const codeBannerCommand = `prefect ${isAgentWorkPool ? "agent" : "worker"} start --pool "${workPoolName}" --work-queue "${workQueueName}"`;
		const codeBannerTitle = `Your work queue ${workQueueName} is ready to go!`;
		const codeBannerSubtitle = `Work queues are scoped to a work pool to allow ${isAgentWorkPool ? "agents" : "workers"} to pull from groups of queues with different priorities.`;

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
					to: ".",
					search: { queueTab: newTab as SearchParams["queueTab"] },
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
									title={codeBannerTitle}
									subtitle={codeBannerSubtitle}
									className="py-0"
								/>
							</div>
						</div>
					</LayoutWellHeader>

					<div className="flex flex-col xl:flex-row xl:gap-8">
						<div className="flex-1">
							<Tabs value={queueTab} onValueChange={handleTabChange}>
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
									<Suspense fallback={<DetailsTabSkeleton />}>
										<WorkPoolQueueDetails
											workPoolName={workPoolName}
											queue={queue}
										/>
									</Suspense>
								</TabsContent>

								<TabsContent value="Upcoming Runs" className="space-y-0">
									<Suspense fallback={<UpcomingRunsTabSkeleton />}>
										<WorkPoolQueueUpcomingRunsTab
											workPoolName={workPoolName}
											queue={queue}
										/>
									</Suspense>
								</TabsContent>

								<TabsContent value="Runs" className="space-y-0">
									<Suspense fallback={<RunsTabSkeleton />}>
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
	},
	loader: async ({ params, context: { queryClient } }) => {
		// Critical data - must await
		const queue = await queryClient.ensureQueryData(
			buildWorkPoolQueueDetailsQuery(params.workPoolName, params.workQueueName),
		);

		// Prefetch work pool details for the CodeBanner (agent-aware command)
		void queryClient.prefetchQuery(buildGetWorkPoolQuery(params.workPoolName));

		return { queue };
	},
	errorComponent: function WorkQueueErrorComponent({
		error,
		reset,
	}: ErrorComponentProps) {
		const serverError = categorizeError(error, "Failed to load work queue");
		if (
			serverError.type !== "server-error" &&
			serverError.type !== "client-error"
		) {
			throw error;
		}
		return (
			<div className="flex flex-col gap-4">
				<div>
					<h1 className="text-2xl font-semibold">Work Queue</h1>
				</div>
				<RouteErrorState error={serverError} onRetry={reset} />
			</div>
		);
	},
	wrapInSuspense: true,
	pendingComponent: PrefectLoading,
});
