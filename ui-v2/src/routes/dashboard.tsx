import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { useCallback, useEffect, useMemo } from "react";
import { z } from "zod";
import { DashboardWorkPoolsCard } from "@/components/dashboard/dashboard-work-pools-card";
import { FlowRunTagsSelect } from "@/components/flow-runs/flow-run-tags-select";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { Switch } from "@/components/ui/switch";

// Search params for dashboard filters (flat structure)
const searchParams = z.object({
	hideSubflows: z.boolean().optional().catch(false),
	tags: z.array(z.string()).optional().catch(undefined),
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

export const Route = createFileRoute("/dashboard")({
	validateSearch: zodValidator(searchParams),
	component: RouteComponent,
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

							<DashboardWorkPoolsCard
								filter={{
									range: {
										start:
											search.from ||
											new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
										end: search.to || new Date().toISOString(),
									},
									flow_runs: {
										start_time_after: search.from
											? new Date(search.from)
											: new Date(Date.now() - 24 * 60 * 60 * 1000),
										start_time_before: search.to
											? new Date(search.to)
											: new Date(),
									},
								}}
							/>
						</div>
					</div>
				</LayoutWellContent>
			</LayoutWell>
		</FlowRunActivityBarGraphTooltipProvider>
	);
}
