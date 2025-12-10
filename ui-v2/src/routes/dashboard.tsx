import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { Suspense, useCallback, useMemo } from "react";
import { z } from "zod";
import { buildFilterDeploymentsQuery } from "@/api/deployments";
import {
	buildAverageLatenessFlowRunsQuery,
	buildCountFlowRunsQuery,
	buildFilterFlowRunsQuery,
	type FlowRunsCountFilter,
	type FlowRunsFilter,
	toFlowRunsCountFilter,
} from "@/api/flow-runs";
import { buildListFlowsQuery } from "@/api/flows";
import {
	buildCountTaskRunsQuery,
	buildGetFlowRunsTaskRunsCountQuery,
	buildTaskRunsHistoryQuery,
	type TaskRunsCountFilter,
} from "@/api/task-runs";
import { buildListWorkPoolQueuesQuery } from "@/api/work-pool-queues";
import {
	buildFilterWorkPoolsQuery,
	buildListWorkPoolWorkersQuery,
} from "@/api/work-pools";
import {
	buildTaskRunsHistoryFilterFromDashboard,
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

/**
 * Pending component shown while the dashboard loader is running.
 * Displays an animated Prefect logo to indicate loading state.
 */
function DashboardPending() {
	return (
		<div className="flex h-full items-center justify-center">
			<svg
				xmlns="http://www.w3.org/2000/svg"
				fill="none"
				viewBox="0 0 76 76"
				className="size-16 animate-pulse text-primary"
				aria-label="Loading Prefect Dashboard"
			>
				<title>Loading</title>
				<path
					fill="currentColor"
					fillRule="evenodd"
					d="M15.89 15.07 38 26.543v22.935l22.104-11.47.007.004V15.068l-.003.001L38 3.598z"
					clipRule="evenodd"
				/>
				<path
					fill="currentColor"
					fillRule="evenodd"
					d="M15.89 15.07 38 26.543v22.935l22.104-11.47.007.004V15.068l-.003.001L38 3.598z"
					clipRule="evenodd"
				/>
				<path
					fill="currentColor"
					fillRule="evenodd"
					d="M37.987 49.464 15.89 38v22.944l.013-.006L38 72.402V49.457z"
					clipRule="evenodd"
				/>
			</svg>
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
	// Rich selector flat params - default to span of last 24 hours
	rangeType: z
		.enum(["span", "range", "around", "period"])
		.optional()
		.default("span")
		.catch("span"),
	seconds: z.number().optional().default(-86400).catch(-86400), // default 24h
	start: z.string().datetime().optional(), // for range
	end: z.string().datetime().optional(),
	aroundDate: z.string().datetime().optional(), // for around
	aroundQuantity: z.number().optional(),
	aroundUnit: z.enum(["second", "minute", "hour", "day"]).optional(),
	period: z.enum(["Today"]).optional(),
});

type DashboardSearch = z.infer<typeof searchParams>;

/**
 * Rounds a date to the nearest minute to stabilize query keys.
 * This prevents cache busting from millisecond differences between renders.
 */
function roundToMinute(date: Date): Date {
	const rounded = new Date(date);
	rounded.setSeconds(0, 0);
	return rounded;
}

function getDateRangeFromSearch(search: DashboardSearch): {
	from: string;
	to: string;
} {
	if (search.from && search.to) {
		return { from: search.from, to: search.to };
	}

	switch (search.rangeType) {
		case "span": {
			const now = roundToMinute(new Date());
			const seconds = search.seconds ?? -86400;
			const then = new Date(now.getTime() + seconds * 1000);
			const [a, b] = [now, then].sort((x, y) => x.getTime() - y.getTime());
			return { from: a.toISOString(), to: b.toISOString() };
		}
		case "range": {
			if (search.start && search.end) {
				return { from: search.start, to: search.end };
			}
			break;
		}
		case "around": {
			if (search.aroundDate && search.aroundQuantity && search.aroundUnit) {
				const center = new Date(search.aroundDate);
				const multiplier = {
					second: 1,
					minute: 60,
					hour: 3600,
					day: 86400,
				}[search.aroundUnit];
				const spanSeconds = search.aroundQuantity * multiplier;
				const from = new Date(center.getTime() - spanSeconds * 1000);
				const to = new Date(center.getTime() + spanSeconds * 1000);
				return { from: from.toISOString(), to: to.toISOString() };
			}
			break;
		}
		case "period": {
			const now = roundToMinute(new Date());
			const start = new Date(now);
			start.setHours(0, 0, 0, 0);
			const end = new Date(now);
			end.setHours(23, 59, 59, 999);
			return { from: start.toISOString(), to: end.toISOString() };
		}
	}

	const now = roundToMinute(new Date());
	const then = new Date(now.getTime() - 86400 * 1000);
	return { from: then.toISOString(), to: now.toISOString() };
}

function buildFlowRunsFilterFromSearch(
	search: DashboardSearch,
): FlowRunsFilter {
	const { from, to } = getDateRangeFromSearch(search);
	const { tags, hideSubflows } = search;

	const baseFilter: FlowRunsFilter = {
		sort: "START_TIME_DESC",
		offset: 0,
	};

	const flowRunsFilterObj: NonNullable<FlowRunsFilter["flow_runs"]> = {
		operator: "and_",
	};

	flowRunsFilterObj.start_time = {
		after_: from,
		before_: to,
	};

	if (tags && tags.length > 0) {
		flowRunsFilterObj.tags = {
			operator: "and_",
			all_: tags,
		};
	}

	if (hideSubflows) {
		flowRunsFilterObj.parent_task_run_id = {
			operator: "and_",
			is_null_: true,
		};
	}

	baseFilter.flow_runs = flowRunsFilterObj;

	return baseFilter;
}

/**
 * Builds task run count filters for prefetching in the loader.
 * This matches the filter logic in TaskRunsCard component.
 */
function buildTaskRunsCountFiltersFromSearch(search: DashboardSearch): {
	total: TaskRunsCountFilter;
	completed: TaskRunsCountFilter;
	failed: TaskRunsCountFilter;
	running: TaskRunsCountFilter;
} {
	const { from, to } = getDateRangeFromSearch(search);
	const { tags, hideSubflows } = search;

	// Build base task_runs filter (matches TaskRunsCard's buildBaseCountFilter)
	const taskRunsFilter: NonNullable<TaskRunsCountFilter["task_runs"]> = {
		operator: "and_",
		// Exclude subflow task runs by default (matches Vue's getBaseFilter)
		subflow_runs: {
			exists_: false,
		},
		start_time: {
			after_: from,
			before_: to,
		},
	};

	// Build flow_runs filter for tags and hideSubflows (matching Vue's dashboard mapping)
	let flowRunsFilter: NonNullable<TaskRunsCountFilter["flow_runs"]> | undefined;
	if ((tags && tags.length > 0) || hideSubflows) {
		flowRunsFilter = {
			operator: "and_",
		};

		// Tags filter on flow_runs (matching Vue's flowRuns.tags.anyName)
		if (tags && tags.length > 0) {
			flowRunsFilter.tags = {
				operator: "and_",
				any_: tags,
			};
		}

		// Hide subflows filter (matching Vue's flowRuns.parentTaskRunIdNull)
		if (hideSubflows) {
			flowRunsFilter.parent_task_run_id = {
				operator: "and_",
				is_null_: true,
			};
		}
	}

	const baseFilter: TaskRunsCountFilter = {
		task_runs: taskRunsFilter,
		...(flowRunsFilter && { flow_runs: flowRunsFilter }),
	};

	// Build filters for each state type (matching Vue's CumulativeTaskRunsCard)
	return {
		total: {
			...baseFilter,
			task_runs: {
				...taskRunsFilter,
				state: {
					operator: "and_",
					type: { any_: ["COMPLETED", "FAILED", "CRASHED", "RUNNING"] },
				},
			},
		},
		completed: {
			...baseFilter,
			task_runs: {
				...taskRunsFilter,
				state: {
					operator: "and_",
					type: { any_: ["COMPLETED"] },
				},
			},
		},
		failed: {
			...baseFilter,
			task_runs: {
				...taskRunsFilter,
				state: {
					operator: "and_",
					type: { any_: ["FAILED", "CRASHED"] },
				},
			},
		},
		running: {
			...baseFilter,
			task_runs: {
				...taskRunsFilter,
				state: {
					operator: "and_",
					type: { any_: ["RUNNING"] },
				},
			},
		},
	};
}

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
	pendingComponent: DashboardPending,
	pendingMs: 400,
	pendingMinMs: 400,
	loaderDeps: ({ search }) => search,
	loader: async ({ deps, context: { queryClient } }) => {
		// Prefetch total flow runs count to determine if dashboard is empty
		const totalFlowRuns = await queryClient.ensureQueryData(
			buildCountFlowRunsQuery({}, 30_000),
		);

		// If there are no flow runs, skip prefetching other data
		if (totalFlowRuns === 0) {
			return;
		}

		// Build the base filter from search params (matches what FlowRunsCard uses)
		const baseFilter = buildFlowRunsFilterFromSearch(deps);
		const { from, to } = getDateRangeFromSearch(deps);

		// Prefetch all flow runs and extract IDs for enrichment queries
		// FlowRunsCard uses useSuspenseQuery for this, so we need to ensure it's prefetched
		const allFlowRuns = await queryClient.ensureQueryData(
			buildFilterFlowRunsQuery(baseFilter, 30_000),
		);

		// Prefetch flows and deployments enrichment data (used by FlowRunsCard)
		// Extract unique flow IDs and deployment IDs from flow runs
		const flowIds = [
			...new Set(
				allFlowRuns
					.map((run) => run.flow_id)
					.filter((id): id is string => Boolean(id)),
			),
		];
		const deploymentIds = [
			...new Set(
				allFlowRuns
					.map((run) => run.deployment_id)
					.filter((id): id is string => Boolean(id)),
			),
		];

		if (flowIds.length > 0) {
			void queryClient.prefetchQuery(
				buildListFlowsQuery({
					flows: { operator: "and_", id: { any_: flowIds } },
					offset: 0,
					sort: "CREATED_DESC",
				}),
			);
		}

		if (deploymentIds.length > 0) {
			void queryClient.prefetchQuery(
				buildFilterDeploymentsQuery({
					deployments: { operator: "and_", id: { any_: deploymentIds } },
					offset: 0,
					sort: "CREATED_DESC",
				}),
			);
		}

		// Prefetch task runs history (used by TaskRunsTrends with useSuspenseQuery)
		const taskRunsHistoryFilter = buildTaskRunsHistoryFilterFromDashboard({
			startDate: from,
			endDate: to,
			tags: deps.tags,
			hideSubflows: deps.hideSubflows,
		});
		void queryClient.prefetchQuery(
			buildTaskRunsHistoryQuery(taskRunsHistoryFilter, 30_000),
		);

		// Convert to count filter (without sort/limit/offset) for count queries
		const countFilter = toFlowRunsCountFilter(baseFilter);

		// Prefetch total count using the count API (used by FlowRunsCard for total display)
		void queryClient.prefetchQuery(
			buildCountFlowRunsQuery(countFilter, 30_000),
		);

		// Prefetch counts for each state type group (used by FlowRunStateTabs)
		STATE_TYPE_GROUPS.forEach((stateTypes) => {
			void queryClient.prefetchQuery(
				buildCountFlowRunsQuery(
					{
						...countFilter,
						flow_runs: {
							...countFilter.flow_runs,
							operator: countFilter.flow_runs?.operator ?? "and_",
							state: { operator: "and_", type: { any_: [...stateTypes] } },
						},
					},
					30_000,
				),
			);
		});

		// Prefetch flow runs for each state type group to minimize loading when switching tabs
		// Also prefetch task run counts for the first 3 runs of each state type (used by FlowRunCard)
		STATE_TYPE_GROUPS.forEach((stateTypes) => {
			const filterWithState: FlowRunsFilter = {
				...baseFilter,
				flow_runs: {
					...baseFilter.flow_runs,
					operator: "and_",
					state: {
						operator: "and_",
						type: {
							any_: [...stateTypes],
						},
					},
				},
			};
			void queryClient
				.fetchQuery(buildFilterFlowRunsQuery(filterWithState, 30_000))
				.then((flowRuns) => {
					if (!flowRuns || flowRuns.length === 0) return;
					// Prefetch task run counts for the first 3 flow runs (matches ITEMS_PER_PAGE in accordion)
					// Each flow run needs its own prefetch to match the query key used by FlowRunTaskRuns component
					const flowRunIds = flowRuns
						.slice(0, 3)
						.map((run) => run.id)
						.filter(Boolean);
					flowRunIds.forEach((flowRunId) => {
						void queryClient.prefetchQuery(
							buildGetFlowRunsTaskRunsCountQuery([flowRunId]),
						);
					});

					// Prefetch flows for accordion (used by FlowRunsAccordion)
					const accordionFlowIds = [
						...new Set(
							flowRuns
								.map((run) => run.flow_id)
								.filter((id): id is string => Boolean(id)),
						),
					];
					if (accordionFlowIds.length > 0) {
						void queryClient.prefetchQuery(
							buildListFlowsQuery({
								flows: { operator: "and_", id: { any_: accordionFlowIds } },
								offset: 0,
								sort: "UPDATED_DESC",
							}),
						);

						// Prefetch per-flow count and last run queries (used by FlowRunsAccordionHeader)
						// This matches the exact filter construction in FlowRunsAccordionHeader component
						accordionFlowIds.forEach((flowId) => {
							// Build filter for this specific flow (matches FlowRunsAccordionHeader.flowFilter)
							const flowFilter: FlowRunsFilter = {
								...filterWithState,
								flows: {
									...(filterWithState.flows ?? {}),
									operator: "and_",
									id: { any_: [flowId] },
								},
							};

							// Prefetch count of flow runs for this flow
							void queryClient.prefetchQuery(
								buildCountFlowRunsQuery(flowFilter, 30_000),
							);

							// Prefetch last flow run for this flow (matches FlowRunsAccordionHeader.lastFlowRunFilter)
							const lastFlowRunFilter: FlowRunsFilter = {
								...flowFilter,
								sort: "START_TIME_DESC",
								limit: 1,
								offset: 0,
							};
							void queryClient.prefetchQuery(
								buildFilterFlowRunsQuery(lastFlowRunFilter, 30_000),
							);
						});
					}
				})
				.catch(() => {
					// Swallow errors so a failed prefetch doesn't break the loader
				});
		});

		// Prefetch task run count queries (used by TaskRunsCard)
		// This matches the 4 count queries made by TaskRunsCard component
		const taskRunsCountFilters = buildTaskRunsCountFiltersFromSearch(deps);
		void queryClient.prefetchQuery(
			buildCountTaskRunsQuery(taskRunsCountFilters.total, 30_000),
		);
		void queryClient.prefetchQuery(
			buildCountTaskRunsQuery(taskRunsCountFilters.completed, 30_000),
		);
		void queryClient.prefetchQuery(
			buildCountTaskRunsQuery(taskRunsCountFilters.failed, 30_000),
		);
		void queryClient.prefetchQuery(
			buildCountTaskRunsQuery(taskRunsCountFilters.running, 30_000),
		);

		// Prefetch work pools data for the dashboard
		const workPools = await queryClient.ensureQueryData(
			buildFilterWorkPoolsQuery({ offset: 0 }),
		);

		// Prefetch nested queries for each active work pool to minimize loading states
		const activeWorkPools = workPools.filter((pool) => !pool.is_paused);
		activeWorkPools.forEach((workPool) => {
			// Prefetch workers and queues (existing)
			void queryClient.prefetchQuery(
				buildListWorkPoolWorkersQuery(workPool.name),
			);
			void queryClient.prefetchQuery(
				buildListWorkPoolQueuesQuery(workPool.name),
			);

			// Build base flow runs filter for this work pool (matches DashboardWorkPoolCard)
			const workPoolFlowRunsFilter: FlowRunsFilter = {
				sort: "ID_DESC",
				offset: 0,
				work_pools: {
					operator: "and_",
					id: { any_: [workPool.id] },
				},
				flow_runs: {
					operator: "and_",
					start_time: {
						after_: from,
						before_: to,
					},
				},
			};

			// Prefetch mini bar chart flow runs (used by WorkPoolMiniBarChart)
			const miniBarChartFilter: FlowRunsFilter = {
				limit: 24,
				sort: "START_TIME_DESC",
				offset: 0,
				work_pools: {
					operator: "and_",
					id: { any_: [workPool.id] },
				},
				flow_runs: {
					operator: "and_",
					start_time: {
						after_: from,
						before_: to,
					},
				},
			};
			void queryClient.prefetchQuery(
				buildFilterFlowRunsQuery(miniBarChartFilter, 30_000),
			);

			// Prefetch completeness stats (used by WorkPoolFlowRunCompleteness)
			// All runs filter (completed, failed, crashed)
			const allRunsFilter: FlowRunsCountFilter = {
				...workPoolFlowRunsFilter,
				work_pools: {
					operator: "and_",
					id: { any_: [workPool.id] },
				},
				flow_runs: {
					operator: "and_",
					start_time: {
						after_: from,
						before_: to,
					},
					state: {
						operator: "and_",
						type: {
							any_: ["COMPLETED", "FAILED", "CRASHED"],
						},
					},
				},
			};
			void queryClient.prefetchQuery(
				buildCountFlowRunsQuery(allRunsFilter, 30_000),
			);

			// Completed runs filter
			const completedRunsFilter: FlowRunsCountFilter = {
				...workPoolFlowRunsFilter,
				work_pools: {
					operator: "and_",
					id: { any_: [workPool.id] },
				},
				flow_runs: {
					operator: "and_",
					start_time: {
						after_: from,
						before_: to,
					},
					state: {
						operator: "and_",
						type: {
							any_: ["COMPLETED"],
						},
					},
				},
			};
			void queryClient.prefetchQuery(
				buildCountFlowRunsQuery(completedRunsFilter, 30_000),
			);

			// Prefetch late count (used by DashboardWorkPoolLateCount)
			const lateFlowRunsFilter: FlowRunsCountFilter = {
				...workPoolFlowRunsFilter,
				work_pools: {
					operator: "and_",
					name: { any_: [workPool.name] },
				},
				flow_runs: {
					operator: "and_",
					start_time: {
						after_: from,
						before_: to,
					},
					state: {
						operator: "and_",
						name: {
							any_: ["Late"],
						},
					},
				},
			};
			void queryClient.prefetchQuery(
				buildCountFlowRunsQuery(lateFlowRunsFilter, 30_000),
			);

			// Prefetch average lateness (used by WorkPoolAverageLateTime)
			const latenessFilter: FlowRunsFilter = {
				sort: "ID_DESC",
				offset: 0,
				work_pools: {
					operator: "and_",
					id: { any_: [workPool.id] },
				},
				flow_runs: {
					operator: "and_",
					start_time: {
						after_: from,
						before_: to,
					},
				},
			};
			void queryClient.prefetchQuery(
				buildAverageLatenessFlowRunsQuery(latenessFilter, 30_000),
			);

			// Prefetch total count (used by DashboardWorkPoolFlowRunsTotal)
			const totalCountFilter: FlowRunsCountFilter = {
				...workPoolFlowRunsFilter,
				work_pools: {
					operator: "and_",
					name: { any_: [workPool.name] },
				},
				flow_runs: {
					operator: "and_",
					start_time: {
						after_: from,
						before_: to,
					},
					state: {
						operator: "and_",
						type: {
							any_: ["COMPLETED", "FAILED", "CRASHED"],
						},
					},
				},
			};
			void queryClient.prefetchQuery(
				buildCountFlowRunsQuery(totalCountFilter, 30_000),
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

	// Compute the date range from search params (defaults are set in zod schema)
	const { from, to } = getDateRangeFromSearch(search);

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
											startDate: from,
											endDate: to,
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
											startDate: from,
											endDate: to,
											tags: search.tags,
											hideSubflows: search.hideSubflows,
										}}
									/>
								</Suspense>

								<Suspense fallback={<WorkPoolsCardSkeleton />}>
									<DashboardWorkPoolsCard
										filter={{
											startDate: from,
											endDate: to,
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
