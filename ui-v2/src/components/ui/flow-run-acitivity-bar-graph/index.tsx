import { Bar, BarChart, Cell, type TooltipProps } from "recharts";
import { ChartContainer, ChartTooltip } from "@/components/ui/chart";
import type { components } from "@/api/prefect";
import { useEffect, useRef, useState } from "react";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "../card";
import { Calendar, ChevronRight, Clock, Rocket } from "lucide-react";
import { StateBadge } from "../state-badge";
import { Link } from "@tanstack/react-router";
import { format } from "date-fns";
import { secondsToApproximateString } from "@/lib/duration";
import { TagBadgeGroup } from "../tag-badge-group";
import { organizeFlowRunsWithGaps } from "./utils";

interface CustomShapeProps {
	fill?: string;
	x?: number;
	y?: number;
	width?: number;
	height?: number;
	radius?: number[];
	role?: string;
	flowRun?: EnrichedFlowRun;
}

const CustomBar = (props: CustomShapeProps) => {
	const minHeight = 4; // Minimum height for zero values
	const {
		x = 0,
		y = 0,
		width = 0,
		height = minHeight,
		radius = [0, 0, 0, 0],
		fill,
		role,
		flowRun,
	} = props;

	return (
		<g role={role}>
			<rect
				data-testid={`bar-rect-${flowRun?.id}`}
				x={x}
				y={y + height - Math.max(height, minHeight, width)}
				width={width}
				height={Math.max(height, minHeight)}
				rx={radius[0]}
				ry={radius[0]}
				fill={fill}
			/>
		</g>
	);
};

type EnrichedFlowRun = components["schemas"]["FlowRun"] & {
	deployment: components["schemas"]["DeploymentResponse"];
	flow: components["schemas"]["Flow"];
};

/**
 * Custom hook to manage tooltip active state with a delayed hide effect. When the tooltip is set to inactive, it will wait for the specified delay before
 * surrendering control.
 *
 * @param initialValue - Initial active state of the tooltip (default: undefined)
 * @param leaveDelay - Delay in milliseconds before hiding the tooltip after becoming inactive (default: 500ms)
 * @returns A tuple containing [isActive, setIsActive] where isActive is the current tooltip state
 *          and setIsActive is a function to update the internal state
 */
const useIsTooltipActive = (
	initialValue: boolean | undefined = undefined,
	leaveDelay = 500,
) => {
	const [internalValue, setInternalValue] = useState<boolean | undefined>(
		initialValue,
	);
	const [externalValue, setExternalValue] = useState<boolean | undefined>(
		initialValue,
	);

	useEffect(() => {
		if (internalValue) {
			setExternalValue(true);
		} else {
			const timer = setTimeout(() => {
				setExternalValue(undefined);
			}, leaveDelay);
			return () => clearTimeout(timer);
		}
	}, [internalValue, leaveDelay]);

	return [externalValue, setInternalValue] as const;
};

type FlowRunActivityBarChartProps = {
	enrichedFlowRuns: EnrichedFlowRun[];
	startDate: Date;
	endDate: Date;
	className?: string;
	barWidth?: number;
	barGap?: number;
	numberOfBars: number;
};

export const FlowRunActivityBarChart = ({
	enrichedFlowRuns,
	startDate,
	endDate,
	barWidth = 8,
	numberOfBars,
	className,
}: FlowRunActivityBarChartProps) => {
	const [isTooltipActive, setIsTooltipActive] = useIsTooltipActive();
	const containerRef = useRef<HTMLDivElement>(null);
	const buckets = organizeFlowRunsWithGaps(
		enrichedFlowRuns,
		startDate,
		endDate,
		numberOfBars,
	);

	const data = buckets.map((flowRun) => ({
		value: flowRun?.total_run_time,
		id: flowRun?.id,
		stateType: flowRun?.state_type,
		flowRun,
	}));
	return (
		<ChartContainer
			ref={containerRef}
			config={{
				inactivity: {
					color: "hsl(210 40% 45%)",
				},
			}}
			className={className}
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
				role="graphics-document"
			>
				<ChartTooltip
					content={<FlowRunTooltip />}
					position={{
						y: containerRef.current?.getBoundingClientRect().height ?? 0,
					}}
					isAnimationActive={false}
					allowEscapeViewBox={{ x: true, y: true }}
					active={isTooltipActive}
					// Allows the tooltip to react to mouse events
					wrapperStyle={{ pointerEvents: "auto" }}
					cursor={true}
				/>
				<Bar
					dataKey="value"
					shape={<CustomBar />}
					radius={[5, 5, 5, 5]}
					onMouseEnter={() => setIsTooltipActive(true)}
					onMouseLeave={() => setIsTooltipActive(undefined)}
				>
					{data.map((entry) => (
						<Cell
							key={`cell-${entry.id}`}
							fill={
								entry.stateType
									? `hsl(var(--state-${entry.stateType?.toLowerCase()}))`
									: "var(--color-inactivity)"
							}
							role="graphics-symbol"
						/>
					))}
				</Bar>
			</BarChart>
		</ChartContainer>
	);
};

type FlowRunTooltipProps = TooltipProps<number, string>;

const FlowRunTooltip = ({ payload, active }: FlowRunTooltipProps) => {
	if (!active || !payload || !payload.length) {
		return null;
	}
	const nestedPayload: unknown = payload[0]?.payload;
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
	if (!flow || !flow.id) {
		return null;
	}
	const deployment = flowRun.deployment;

	const startTime = flowRun.start_time
		? new Date(flowRun.start_time)
		: flowRun.expected_start_time
			? new Date(flowRun.expected_start_time)
			: null;

	return (
		<Card className="-translate-x-1/2">
			<CardHeader>
				<CardTitle className="flex items-center gap-1">
					<Link
						to={"/flows/flow/$id"}
						params={{ id: flow.id }}
						className="text-base font-medium"
					>
						{flowRun.flow.name}
					</Link>
					<ChevronRight className="w-4 h-4" />
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
						<StateBadge state={flowRun.state} />
					</CardDescription>
				)}
			</CardHeader>
			<CardContent className="flex flex-col gap-1">
				{deployment?.id && (
					<Link
						to={"/deployments/deployment/$id"}
						params={{ id: deployment.id }}
						className="flex items-center gap-1"
					>
						<Rocket className="w-4 h-4" />
						<p className="text-sm font-medium whitespace-nowrap">
							{deployment.name}
						</p>
					</Link>
				)}
				<span className="flex items-center gap-1">
					<Clock className="w-4 h-4" />
					<p className="text-sm whitespace-nowrap">
						{secondsToApproximateString(flowRun.total_run_time)}
					</p>
				</span>
				{startTime && (
					<span className="flex items-center gap-1">
						<Calendar className="w-4 h-4" />
						<p className="text-sm">
							{format(startTime, "yyyy/MM/dd hh:mm a")}
						</p>
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
