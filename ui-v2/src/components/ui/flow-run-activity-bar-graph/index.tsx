import { Link } from "@tanstack/react-router";
import { cva } from "class-variance-authority";
import { format, formatDistanceStrict } from "date-fns";
import { Calendar, ChevronRight, Clock } from "lucide-react";
import type { ReactNode } from "react";
import { useCallback, useContext, useEffect, useState } from "react";
import { Bar, BarChart, Cell, type TooltipContentProps } from "recharts";
import type { components } from "@/api/prefect";
import { DeploymentIconText } from "@/components/deployments/deployment-icon-text";
import { ChartContainer, ChartTooltip } from "@/components/ui/chart";
import { cn } from "@/utils";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "../card";
import { StateBadge } from "../state-badge";
import { TagBadgeGroup } from "../tag-badge-group";
import { FlowRunActivityBarGraphTooltipContext } from "./context";
import { organizeFlowRunsWithGaps } from "./utils";

type CustomShapeProps = {
	x?: number;
	y?: number;
	width?: number;
	height?: number;
	radius?: number[];
	role?: string;
	flowRun?: EnrichedFlowRun;
};

const barVariants = cva("gap-1 z-1", {
	variants: {
		state: {
			COMPLETED: "fill-green-600",
			FAILED: "fill-red-600",
			RUNNING: "fill-blue-700",
			CANCELLED: "fill-gray-500",
			CANCELLING: "fill-gray-600",
			CRASHED: "fill-orange-600",
			PAUSED: "fill-gray-500",
			PENDING: "fill-gray-400",
			SCHEDULED: "fill-yellow-400",
			NONE: "fill-gray-300",
		} satisfies Record<components["schemas"]["StateType"] | "NONE", string>,
	},
	defaultVariants: {
		state: "NONE",
	},
});

const CustomBar = (props: CustomShapeProps) => {
	const minHeight = 8; // Minimum height for zero values
	const {
		x = 0,
		y = 0,
		width = 0,
		height = minHeight,
		radius = [0, 0, 0, 0],
		role,
		flowRun,
	} = props;
	const effectiveHeight = Math.max(height, minHeight);
	// Shift the bar up if we're inflating its height, so it still rests on the baseline
	const yPosition = y + (height - effectiveHeight);

	return (
		<g role={role}>
			<rect
				data-testid={`bar-rect-${flowRun?.id}`}
				x={x}
				y={yPosition}
				width={width}
				height={effectiveHeight}
				rx={radius[0]}
				ry={radius[0]}
				className={barVariants({ state: flowRun?.state_type })}
			/>
		</g>
	);
};

type EnrichedFlowRun = components["schemas"]["FlowRunResponse"] & {
	deployment?: components["schemas"]["DeploymentResponse"];
	flow?: components["schemas"]["Flow"];
};

/**
 * Custom hook to manage tooltip active state with a delayed hide effect and coordinate between multiple tooltips.
 * Only one tooltip can be active at a time, controlled by the holder ID.
 *
 * @param chartId - Unique identifier for the chart instance to coordinate with other charts
 * @param initialValue - Initial active state of the tooltip (default: undefined)
 * @param leaveDelay - Delay in milliseconds before hiding the tooltip after becoming inactive (default: 200ms)
 * @returns A tuple containing [isActive, setIsActive] where isActive is the current tooltip state
 *          and setIsActive is a function to update the internal state. isActive will be false if another
 *          chart takes control.
 */
const useIsTooltipActive = (
	chartId?: string,
	initialValue: boolean | undefined = undefined,
	leaveDelay = 200,
) => {
	const [internalValue, setInternalValue] = useState<boolean | undefined>(
		initialValue,
	);
	const [externalValue, setExternalValue] = useState<boolean | undefined>(
		initialValue,
	);
	const { currentHolder, takeCurrentHolder, releaseCurrentHolder } = useContext(
		FlowRunActivityBarGraphTooltipContext,
	);

	useEffect(() => {
		if (currentHolder && chartId !== currentHolder) {
			setExternalValue(false);
		} else if (internalValue) {
			if (chartId) {
				takeCurrentHolder(chartId);
			}
			setExternalValue(true);
		} else {
			const timer = setTimeout(() => {
				setExternalValue(undefined);
				if (chartId) {
					releaseCurrentHolder(chartId);
				}
			}, leaveDelay);
			return () => clearTimeout(timer);
		}
	}, [
		internalValue,
		leaveDelay,
		chartId,
		currentHolder,
		takeCurrentHolder,
		releaseCurrentHolder,
	]);

	return [externalValue, setInternalValue] as const;
};

/**
 * Provider component for FlowRunActivityBarGraphTooltipContext.
 * Manages tooltip state across multiple charts by tracking which chart is currently displaying a tooltip.
 */
export const FlowRunActivityBarGraphTooltipProvider = ({
	children,
}: {
	children: ReactNode;
}) => {
	const [currentHolder, setCurrentHolder] = useState<string | undefined>(
		undefined,
	);

	const takeCurrentHolder = useCallback((holder: string) => {
		setCurrentHolder(holder);
	}, []);

	const releaseCurrentHolder = useCallback(
		(holder: string) => {
			if (currentHolder === holder) {
				setCurrentHolder(undefined);
			}
		},
		[currentHolder],
	);

	return (
		<FlowRunActivityBarGraphTooltipContext.Provider
			value={{ currentHolder, takeCurrentHolder, releaseCurrentHolder }}
		>
			{children}
		</FlowRunActivityBarGraphTooltipContext.Provider>
	);
};

type FlowRunActivityBarChartProps = {
	chartId?: string;
	enrichedFlowRuns: EnrichedFlowRun[];
	startDate: Date;
	endDate: Date;
	className?: string;
	barWidth?: number;
	barGap?: number;
	numberOfBars: number;
};

export const FlowRunActivityBarChart = ({
	chartId,
	enrichedFlowRuns,
	startDate,
	endDate,
	barWidth = 8,
	numberOfBars,
	className,
}: FlowRunActivityBarChartProps) => {
	const [isTooltipActive, setIsTooltipActive] = useIsTooltipActive(chartId);

	// Cap flow runs to prevent crash when there are more runs than bars.
	// The chart can only display one run per bar, so we take the first N runs
	// (which are typically the most recent due to query sort order).
	const cappedFlowRuns = enrichedFlowRuns.slice(0, numberOfBars);

	const buckets = organizeFlowRunsWithGaps(
		cappedFlowRuns,
		startDate,
		endDate,
		numberOfBars,
	);

	const data = buckets.map((flowRun, index) => ({
		value: flowRun?.total_run_time ?? 0,
		id: flowRun?.id ?? `empty-${index}`,
		stateType: flowRun?.state_type,
		flowRun,
	}));

	return (
		<ChartContainer
			config={{
				inactivity: {
					color: "hsl(210 40% 45%)",
				},
			}}
			className={cn("relative", className, isTooltipActive && "z-20")}
		>
			<BarChart
				data={data}
				margin={{ top: 0, right: 0, bottom: 0, left: 0 }}
				barSize={barWidth}
				onMouseMove={() => {
					setIsTooltipActive(true);
				}}
				onMouseLeave={() => {
					setIsTooltipActive(undefined);
				}}
			>
				<ChartTooltip
					content={<FlowRunTooltip />}
					isAnimationActive={false}
					allowEscapeViewBox={{ x: true, y: true }}
					active={isTooltipActive}
					// Allows the tooltip to react to mouse events
					wrapperStyle={{ pointerEvents: "auto" }}
				/>
				<Bar
					dataKey="value"
					shape={<CustomBar />}
					radius={[5, 5, 5, 5]}
					onMouseEnter={() => setIsTooltipActive(true)}
					onMouseLeave={() => setIsTooltipActive(undefined)}
					isAnimationActive={false}
				>
					{data.map((entry) => (
						<Cell key={`cell-${entry.id}`} role="graphics-symbol" />
					))}
				</Bar>
			</BarChart>
		</ChartContainer>
	);
};

FlowRunActivityBarChart.displayName = "FlowRunActivityBarChart";

type FlowRunTooltipProps = Partial<TooltipContentProps<number, string>>;

const FlowRunTooltip = ({ payload, active }: FlowRunTooltipProps) => {
	if (!active || !payload || !payload.length) {
		return null;
	}
	const firstPayloadItem = payload[0] as { payload?: unknown } | undefined;
	const nestedPayload: unknown = firstPayloadItem?.payload;
	if (
		!nestedPayload ||
		typeof nestedPayload !== "object" ||
		!("flowRun" in nestedPayload)
	) {
		return null;
	}
	const flowRun = nestedPayload.flowRun as EnrichedFlowRun;
	if (!flowRun || !flowRun.id) {
		return null;
	}

	const flow = flowRun.flow;
	const deployment = flowRun.deployment;

	const startTime = flowRun.start_time
		? new Date(flowRun.start_time)
		: flowRun.expected_start_time
			? new Date(flowRun.expected_start_time)
			: null;

	return (
		<Card>
			<CardHeader>
				<CardTitle className="flex items-center gap-1">
					{flow?.id && (
						<>
							<Link
								to={"/flows/flow/$id"}
								params={{ id: flow.id }}
								className="text-base font-medium"
							>
								{flow.name}
							</Link>
							<ChevronRight className="size-4" />
						</>
					)}
					<Link
						to={"/runs/flow-run/$id"}
						params={{ id: flowRun.id }}
						className="text-base font-medium"
					>
						{flowRun.name}
					</Link>
				</CardTitle>
				{flowRun.state && (
					<CardDescription>
						<StateBadge type={flowRun.state.type} name={flowRun.state.name} />
					</CardDescription>
				)}
			</CardHeader>
			<CardContent className="flex flex-col gap-1">
				{deployment?.id && (
					<DeploymentIconText
						deployment={deployment}
						className="flex items-center gap-1 text-sm font-medium whitespace-nowrap"
					/>
				)}
				<span className="flex items-center gap-1">
					<Clock className="size-4" />
					<p className="text-sm whitespace-nowrap">
						{formatDistanceStrict(0, flowRun.total_run_time * 1000, {
							addSuffix: false,
						})}
					</p>
				</span>
				{startTime && (
					<span className="flex items-center gap-1">
						<Calendar className="size-4" />
						<p className="text-sm">{format(startTime, "yyyy/MM/dd hh:mm a")}</p>
					</span>
				)}
				<div>
					<TagBadgeGroup tags={flowRun.tags ?? []} maxTagsDisplayed={5} />
				</div>
			</CardContent>
		</Card>
	);
};

FlowRunTooltip.displayName = "FlowRunTooltip";
