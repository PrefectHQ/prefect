import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { Suspense, useCallback, useEffect, useMemo } from "react";
import { z } from "zod";
import {
	buildCountFlowRunsQuery,
	buildFilterFlowRunsQuery,
	type FlowRunsFilter,
} from "@/api/flow-runs";
import { buildListWorkPoolQueuesQuery } from "@/api/work-pool-queues";
import {
	buildFilterWorkPoolsQuery,
	buildListWorkPoolWorkersQuery,
} from "@/api/work-pools";
import {
	DashboardFlowRunsEmptyState,
	DashboardWorkPoolsCard,
	FlowRunsCard,
	TaskRunsCard,
} from "@/components/dashboard";
import { FlowRunTagsSelect } from "@/components/flow-runs/flow-run-tags-select";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";
import {
	type DateRangeSelectAroundUnit,
	type DateRangeSelectValue,
	RichDateRangeSelector,
} from "@/components/ui/date-range-select";
import { FlowRunActivityBarGraphTooltipProvider } from "@/components/ui/flow-run-activity-bar-graph";
import { Label } from "@/components/ui/label";
import {
	LayoutWell,
	LayoutWellContent,
	LayoutWellHeader,
} from "@/components/ui/layout-well";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";

function FlowRunsCardSkeleton() {
	return (
		<div className="rounded-lg border bg-card text-card-foreground shadow-sm">
			<div className="flex flex-row items-center justify-between p-6 pb-2">
				<Skeleton className="h-6 w-24" />
				<Skeleton className="h-4 w-16" />
			</div>
			<div className="p-6 pt-0 space-y-2">
				<Skeleton className="h-24 w-full" />
				<div className="flex justify-between w-full gap-2">
					{[1, 2, 3, 4, 5].map((i) => (
						<Skeleton key={i} className="h-10 flex-1" />
					))}
				</div>
				<Skeleton className="h-32 w-full" />
			</div>
		</div>
	);
}

function TaskRunsCardSkeleton() {
	return (
		<div className="rounded-lg border bg-card text-card-foreground shadow-sm">
			<div className="flex flex-row items-center justify-between p-6 pb-2">
				<Skeleton className="h-6 w-24" />
			</div>
			<div className="p-6 pt-0 space-y-4">
				<div className="grid gap-1">
					<Skeleton className="h-5 w-20" />
					<Skeleton className="h-4 w-32" />
					<Skeleton className="h-4 w-28" />
				</div>
				<Skeleton className="h-16 w-full" />
			</div>
		</div>
	);
}

function WorkPoolsCardSkeleton() {
	return (
		<div className="rounded-lg border bg-card text-card-foreground shadow-sm">
			<div className="p-6">
				<Skeleton className="h-6 w-32 mb-4" />
			</div>
			<div className="p-6 pt-0 space-y-4">
				<div className="rounded-xl border p-3 space-y-3">
					<div className="flex items-center gap-2">
						<Skeleton className="h-5 w-32" />
						<Skeleton className="h-5 w-5 rounded-full" />
					</div>
					<div className="grid grid-cols-4 gap-2">
						{[1, 2, 3, 4].map((i) => (
							<div key={i} className="space-y-1">
								<Skeleton className="h-3 w-16" />
								<Skeleton className="h-4 w-12" />
							</div>
						))}
					</div>
				</div>
			</div>
		</div>
	);
}

// Valid tab values for flow run state filtering
const FLOW_RUN_STATE_TABS = [
	"FAILED-CRASHED",
	"RUNNING-PENDING-CANCELLING",
	"COMPLETED",
	"SCHEDULED-PAUSED",
	"CANCELLED",
] as const;

type FlowRunStateTab = (typeof FLOW_RUN_STATE_TABS)[number];

// Search params for dashboard filters (flat structure)
const searchParams = z.object({
	hideSubflows: z.boolean().optional().catch(false),
	tags: z.array(z.string()).optional().catch(undefined),
	// Flow run state tab selection (defaults to FAILED-CRASHED)
	tab: z.enum(FLOW_RUN_STATE_TABS).optional().catch(undefined),
	// Derived normalized range for downstream queries
	from: z.string().datetime().optional().catch(undefined),
	to: z.string().datetime().optional().catch(undefined),
	// Rich selector flat params
	rangeType: z.enum(["span", "range", "around", "period"]).optional(),
	seconds: z.number().optional(), // for span
	start: z.string().datetime().optional(), // for range
	end: z.string().datetime().optional(),
	aroundDate: z.string().datetime().optional(), // for around
	aroundQuantity: z.number().optional(),
	aroundUnit: z.enum(["second", "minute", "hour", "day"]).optional(),
	period: z.enum(["Today"]).optional(),
});

const STATE_TYPE_GROUPS = [
	["FAILED", "CRASHED"],
	["RUNNING", "PENDING", "CANCELLING"],
	["COMPLETED"],
	["SCHEDULED", "PAUSED"],
	["CANCELLED"],
] as const;

export const Route = createFileRoute("/dashboard")({
	validateSearch: zodValidator(searchParams),
	component: RouteComponent,
	loader: async ({ context: { queryClient } }) => {
		// Prefetch total flow runs count to determine if dashboard is empty
		const totalFlowRuns = await queryClient.ensureQueryData(
			buildCountFlowRunsQuery({}, 30_000),
		);

		// If there are no flow runs, skip prefetching other data
		if (totalFlowRuns === 0) {
			return;
		}

		// Prefetch all flow runs with basic filter (used by FlowRunsCard)
		// Note: Components may add date/tag filters, but this prefetch helps with initial load
		void queryClient.prefetchQuery(
			buildFilterFlowRunsQuery(
				{
					sort: "START_TIME_DESC",
					offset: 0,
				},
				30_000,
			),
		);

		// Prefetch flow runs for each state type group to minimize loading when switching tabs
		STATE_TYPE_GROUPS.forEach((stateTypes) => {
			const filter: FlowRunsFilter = {
				sort: "START_TIME_DESC",
				offset: 0,
				flow_runs: {
					operator: "and_",
					state: {
						operator: "and_",
						type: {
							any_: [...stateTypes],
						},
					},
				},
			};
			void queryClient.prefetchQuery(buildFilterFlowRunsQuery(filter, 30_000));
		});

		// Prefetch work pools data for the dashboard
		const workPools = await queryClient.ensureQueryData(
			buildFilterWorkPoolsQuery({ offset: 0 }),
		);

		// Prefetch nested queries for each active work pool to minimize loading states
		const activeWorkPools = workPools.filter((pool) => !pool.is_paused);
		activeWorkPools.forEach((workPool) => {
			void queryClient.prefetchQuery(
				buildListWorkPoolWorkersQuery(workPool.name),
			);
			void queryClient.prefetchQuery(
				buildListWorkPoolQueuesQuery(workPool.name),
			);
		});
	},
	wrapInSuspense: true,
});

function omitKeys<T extends object, K extends readonly (keyof T)[]>(
	obj: T,
	keys: K,
): Omit<T, K[number]> {
	const clone: Record<string, unknown> = {
		...(obj as Record<string, unknown>),
	};
	for (const k of keys as readonly string[]) {
		delete clone[k];
	}
	return clone as Omit<T, K[number]>;
}

export function RouteComponent() {
	type DashboardSearch = z.infer<typeof searchParams>;
	const search = Route.useSearch();
	const navigate = Route.useNavigate();

	// Check if there are any flow runs at all (unfiltered count)
	const { data: totalFlowRuns } = useSuspenseQuery(
		buildCountFlowRunsQuery({}, 30_000),
	);
	const isEmpty = totalFlowRuns === 0;

	// Derive UI states with sensible defaults
	const hideSubflows = search.hideSubflows ?? false;
	const tags = search.tags ?? [];
	const dateRangeValue = useMemo<DateRangeSelectValue>(() => {
		switch (search.rangeType) {
			case "span": {
				const seconds = search.seconds ?? -86400; // default 24h
				return { type: "span", seconds };
			}
			case "range": {
				if (search.start && search.end) {
					return {
						type: "range",
						startDate: new Date(search.start),
						endDate: new Date(search.end),
					};
				}
				return { type: "span", seconds: -86400 };
			}
			case "around": {
				if (search.aroundDate && search.aroundQuantity && search.aroundUnit) {
					return {
						type: "around",
						date: new Date(search.aroundDate),
						quantity: search.aroundQuantity,
						unit: search.aroundUnit as DateRangeSelectAroundUnit,
					};
				}
				return { type: "span", seconds: -86400 };
			}
			case "period": {
				return { type: "period", period: search.period ?? "Today" };
			}
			default:
				return { type: "span", seconds: -86400 };
		}
	}, [
		search.rangeType,
		search.seconds,
		search.start,
		search.end,
		search.aroundDate,
		search.aroundQuantity,
		search.aroundUnit,
		search.period,
	]);

	const onToggleHideSubflows = useCallback(
		(checked: boolean) => {
			void navigate({
				to: ".",
				search: (prev) => ({ ...prev, hideSubflows: checked }),
				replace: true,
			});
		},
		[navigate],
	);

	const onTagsChange = useCallback(
		(nextTags: string[]) => {
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					tags: nextTags.length ? nextTags : undefined,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	// Convert tab string to state types array and vice versa
	const selectedStates = useMemo(() => {
		const tab = search.tab ?? "FAILED-CRASHED";
		return tab.split("-") as Array<
			| "FAILED"
			| "CRASHED"
			| "RUNNING"
			| "PENDING"
			| "CANCELLING"
			| "COMPLETED"
			| "SCHEDULED"
			| "PAUSED"
			| "CANCELLED"
		>;
	}, [search.tab]);

	const onTabChange = useCallback(
		(
			states: Array<
				| "FAILED"
				| "CRASHED"
				| "RUNNING"
				| "PENDING"
				| "CANCELLING"
				| "COMPLETED"
				| "SCHEDULED"
				| "PAUSED"
				| "CANCELLED"
			>,
		) => {
			const tabValue = states.join("-") as FlowRunStateTab;
			void navigate({
				to: ".",
				search: (prev) => ({
					...prev,
					// Only set tab if it's not the default (FAILED-CRASHED)
					tab: tabValue === "FAILED-CRASHED" ? undefined : tabValue,
				}),
				replace: true,
			});
		},
		[navigate],
	);

	const onDateRangeChange = useCallback(
		(next: DateRangeSelectValue) => {
			void navigate({
				to: ".",
				search: (prev: DashboardSearch) => {
					if (!next) {
						return omitKeys(prev, [
							"rangeType",
							"seconds",
							"start",
							"end",
							"aroundDate",
							"aroundQuantity",
							"aroundUnit",
							"period",
							"from",
							"to",
						] as const);
					}

					// Compute normalized from/to for convenience
					let fromIso: string | undefined;
					let toIso: string | undefined;
					switch (next.type) {
						case "span": {
							const now = new Date();
							const then = new Date(now.getTime() + next.seconds * 1000);
							const [a, b] = [now, then].sort(
								(x, y) => x.getTime() - y.getTime(),
							);
							fromIso = a.toISOString();
							toIso = b.toISOString();
							return {
								...prev,
								rangeType: "span",
								seconds: next.seconds,
								from: fromIso,
								to: toIso,
							};
						}
						case "range": {
							fromIso = next.startDate.toISOString();
							toIso = next.endDate.toISOString();
							return {
								...prev,
								rangeType: "range",
								start: fromIso,
								end: toIso,
								from: fromIso,
								to: toIso,
							};
						}
						case "around": {
							const center = next.date;
							const multiplier = {
								second: 1,
								minute: 60,
								hour: 3600,
								day: 86400,
							}[next.unit];
							const spanSeconds = next.quantity * multiplier;
							const from = new Date(center.getTime() - spanSeconds * 1000);
							const to = new Date(center.getTime() + spanSeconds * 1000);
							fromIso = from.toISOString();
							toIso = to.toISOString();
							return {
								...prev,
								rangeType: "around",
								aroundDate: center.toISOString(),
								aroundQuantity: next.quantity,
								aroundUnit: next.unit,
								from: fromIso,
								to: toIso,
							};
						}
						case "period": {
							// Only Today supported; normalize to today's start/end
							const now = new Date();
							const start = new Date(now);
							start.setHours(0, 0, 0, 0);
							const end = new Date(now);
							end.setHours(23, 59, 59, 999);
							fromIso = start.toISOString();
							toIso = end.toISOString();
							return {
								...prev,
								rangeType: "period",
								period: next.period,
								from: fromIso,
								to: toIso,
							};
						}
					}
				},
				replace: true,
			});
		},
		[navigate],
	);

	// Initialize default date range to last 24 hours if unset
	useEffect(() => {
		if (!search.rangeType && !search.from && !search.to) {
			// default to a span of last 24 hours
			onDateRangeChange({ type: "span", seconds: -86400 });
		}
	}, [search.rangeType, search.from, search.to, onDateRangeChange]);

	return (
		<FlowRunActivityBarGraphTooltipProvider>
			<LayoutWell>
				<LayoutWellContent>
					<LayoutWellHeader className="pb-4 md:pb-6">
						<div className="flex flex-col space-y-4 md:space-y-0 md:flex-row md:items-center md:justify-between">
							<div>
								<Breadcrumb>
									<BreadcrumbList>
										<BreadcrumbItem className="text-2xl font-bold text-foreground">
											Dashboard
										</BreadcrumbItem>
									</BreadcrumbList>
								</Breadcrumb>
							</div>
							{!isEmpty && (
								<div className="flex flex-col w-full max-w-full gap-2 md:w-auto md:inline-flex md:flex-row items-center">
									{/* Filters */}
									<div className="flex items-center gap-2 w-full md:w-auto">
										<div className="pr-2 w-full md:w-auto flex items-center gap-2">
											<Switch
												id="hide-subflows"
												checked={hideSubflows}
												onCheckedChange={onToggleHideSubflows}
											/>
											<Label htmlFor="hide-subflows">Hide subflows</Label>
										</div>
										<div className="min-w-0 w-60">
											<FlowRunTagsSelect
												value={tags}
												onChange={onTagsChange}
												placeholder="All tags"
											/>
										</div>
										<div className="min-w-0">
											<RichDateRangeSelector
												value={dateRangeValue}
												onValueChange={onDateRangeChange}
												placeholder="Select a time span"
											/>
										</div>
									</div>
								</div>
							)}
						</div>
					</LayoutWellHeader>

					{isEmpty ? (
						<DashboardFlowRunsEmptyState />
					) : (
						<div className="grid grid-cols-1 gap-4 items-start xl:grid-cols-2">
							{/* Main content - Flow Runs Card */}
							<div className="space-y-4">
								<Suspense fallback={<FlowRunsCardSkeleton />}>
									<FlowRunsCard
										filter={{
											startDate: search.from,
											endDate: search.to,
											tags: search.tags,
											hideSubflows: search.hideSubflows,
										}}
										selectedStates={selectedStates}
										onStateChange={onTabChange}
									/>
								</Suspense>
							</div>

							{/* Sidebar - Task Runs and Work Pools Cards */}
							<div className="grid grid-cols-1 gap-4">
								<Suspense fallback={<TaskRunsCardSkeleton />}>
									<TaskRunsCard
										filter={{
											startDate: search.from,
											endDate: search.to,
											tags: search.tags,
										}}
									/>
								</Suspense>

								<Suspense fallback={<WorkPoolsCardSkeleton />}>
									<DashboardWorkPoolsCard
										filter={{
											startDate: search.from,
											endDate: search.to,
										}}
									/>
								</Suspense>
							</div>
						</div>
					)}
				</LayoutWellContent>
			</LayoutWell>
		</FlowRunActivityBarGraphTooltipProvider>
	);
}
