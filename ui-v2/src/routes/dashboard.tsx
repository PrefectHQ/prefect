import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { buildListFlowRunTagsQuery } from "@/api/flow-runs";
import {
	DateRangeSelect,
	type DateRangeValue,
	dashboardFilterSchema,
	FlowRunTagsInput,
	SubflowToggle,
} from "@/components/dashboard/filters";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
	LayoutWell,
	LayoutWellContent,
	LayoutWellHeader,
} from "@/components/ui/layout-well";

export const Route = createFileRoute("/dashboard")({
	validateSearch: zodValidator(dashboardFilterSchema),
	component: RouteComponent,
	loader: ({ context: { queryClient } }) => {
		// Prefetch available tags for the filter
		void queryClient.prefetchQuery(buildListFlowRunTagsQuery());
	},
});

export function RouteComponent() {
	const search = Route.useSearch();
	const navigate = Route.useNavigate();
	const { data: availableTags = [] } = useSuspenseQuery(
		buildListFlowRunTagsQuery(),
	);

	// Parse the date range from URL parameters
	const dateRange: DateRangeValue = (() => {
		if (!search.dateRangeType) return null;

		if (
			search.dateRangeType === "span" &&
			search.dateRangeSeconds !== undefined
		) {
			return { type: "span", seconds: search.dateRangeSeconds };
		}

		if (
			search.dateRangeType === "range" &&
			search.dateRangeStart &&
			search.dateRangeEnd
		) {
			return {
				type: "range",
				startDate: new Date(search.dateRangeStart),
				endDate: new Date(search.dateRangeEnd),
			};
		}

		return null;
	})();

	// Filter update handlers
	const updateTags = (tags: string[]) => {
		void navigate({
			to: ".",
			search: (prev) => ({
				...prev,
				tags: tags.length > 0 ? tags : undefined,
			}),
			replace: true,
		});
	};

	const updateHideSubflows = (hideSubflows: boolean) => {
		void navigate({
			to: ".",
			search: (prev) => ({
				...prev,
				hideSubflows: hideSubflows || undefined,
			}),
			replace: true,
		});
	};

	const updateDateRange = (newDateRange: DateRangeValue) => {
		void navigate({
			to: ".",
			search: (prev) => {
				if (!newDateRange) {
					const {
						dateRangeType: _dateRangeType,
						dateRangeSeconds: _dateRangeSeconds,
						dateRangeStart: _dateRangeStart,
						dateRangeEnd: _dateRangeEnd,
						...rest
					} = prev;
					return rest;
				}

				if (newDateRange.type === "span") {
					return {
						...prev,
						dateRangeType: "span" as const,
						dateRangeSeconds: newDateRange.seconds,
						dateRangeStart: undefined,
						dateRangeEnd: undefined,
					};
				}

				if (newDateRange.type === "range") {
					return {
						...prev,
						dateRangeType: "range" as const,
						dateRangeStart: newDateRange.startDate.toISOString(),
						dateRangeEnd: newDateRange.endDate.toISOString(),
						dateRangeSeconds: undefined,
					};
				}

				return prev;
			},
			replace: true,
		});
	};

	return (
		<LayoutWell>
			<LayoutWellContent>
				<LayoutWellHeader>
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
						<div className="flex flex-col w-full max-w-full gap-2 md:w-auto md:inline-flex md:flex-row items-center">
							{/* Dashboard filter controls */}
							<div className="flex flex-col gap-2 md:flex-row md:items-center">
								<SubflowToggle
									value={search.hideSubflows}
									onChange={updateHideSubflows}
								/>
								<FlowRunTagsInput
									value={search.tags}
									onChange={updateTags}
									availableTags={availableTags}
									placeholder="Filter by tags"
								/>
								<DateRangeSelect
									value={dateRange}
									onChange={updateDateRange}
									placeholder="Select time range"
								/>
							</div>
						</div>
					</div>
				</LayoutWellHeader>

				<div className="grid grid-cols-1 gap-4 items-start xl:grid-cols-2">
					{/* Main content - Flow Runs Card */}
					<div className="space-y-4">
						<Card>
							<CardHeader>
								<CardTitle>Flow Runs</CardTitle>
							</CardHeader>
							<CardContent className="space-y-4">
								<div className="h-64 bg-muted rounded-md flex items-center justify-center">
									<span className="text-muted-foreground">
										Flow runs chart and table will appear here
									</span>
								</div>
							</CardContent>
						</Card>
					</div>

					{/* Sidebar - Task Runs and Work Pools Cards */}
					<div className="grid grid-cols-1 gap-4">
						<Card>
							<CardHeader>
								<CardTitle>Cumulative Task Runs</CardTitle>
							</CardHeader>
							<CardContent>
								<div className="h-48 bg-muted rounded-md flex items-center justify-center">
									<span className="text-muted-foreground">
										Cumulative task runs chart will appear here
									</span>
								</div>
							</CardContent>
						</Card>

						<Card>
							<CardHeader>
								<CardTitle>Work Pools</CardTitle>
							</CardHeader>
							<CardContent>
								<div className="h-48 bg-muted rounded-md flex items-center justify-center">
									<span className="text-muted-foreground">
										Work pools status will appear here
									</span>
								</div>
							</CardContent>
						</Card>
					</div>
				</div>
			</LayoutWellContent>
		</LayoutWell>
	);
}
