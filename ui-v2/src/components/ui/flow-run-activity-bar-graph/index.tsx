import { Link } from "@tanstack/react-router";
import { cva } from "class-variance-authority";
import { format, formatDistanceStrict } from "date-fns";
import { Calendar, ChevronRight, Clock, Rocket } from "lucide-react";
import type { ReactNode } from "react";
import {
	type RefObject,
	useCallback,
	useContext,
	useEffect,
	useRef,
	useState,
} from "react";
import { createPortal } from "react-dom";
import { Bar, BarChart, Cell, type TooltipProps } from "recharts";
import type { Coordinate } from "recharts/types/util/types";
import type { components } from "@/api/prefect";
import { ChartContainer, ChartTooltip } from "@/components/ui/chart";
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
	containerHeight?: number;
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
		width = 0,
		height = minHeight,
		radius = [0, 0, 0, 0],
		role,
		flowRun,
		containerHeight = 32,
	} = props;
	const effectiveHeight = Math.max(height, minHeight);
	const yPosition = containerHeight - effectiveHeight;

	return (
		<g role={role}>
			<rect
				data-testid={`bar-rect-${flowRun?.id}`}
				x={x}
				y={yPosition}
				width={width}
				height={Math.max(height, minHeight)}
				rx={radius[0]}
				ry={radius[0]}
				className={barVariants({ state: flowRun?.state_type })}
			/>
		</g>
	);
};

type EnrichedFlowRun = components["schemas"]["FlowRun"] & {
	deployment: components["schemas"]["DeploymentResponse"];
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
	const containerHeight = containerRef.current?.getBoundingClientRect().height;
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
			>
				<ChartTooltip
					content={<FlowRunTooltip containerRef={containerRef} />}
					position={{
						y: containerHeight ?? 0,
					}}
					isAnimationActive={false}
					allowEscapeViewBox={{ x: true, y: true }}
					active={isTooltipActive}
					// Allows the tooltip to react to mouse events
					wrapperStyle={{ pointerEvents: "auto" }}
				/>
				<Bar
					dataKey="value"
					shape={<CustomBar containerHeight={containerHeight} />}
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

/**
 * TooltipPortal is a component that renders tooltips in a portal at the correct position relative to their trigger element.
 * This is necessary because tooltips rendered inside charts can be clipped by the chart's parent's boundaries.
 * By rendering in a portal at the document root, we ensure the tooltip is always visible and correctly positioned.
 *
 * The component takes a containerRef to calculate positioning relative to the chart container,
 * along with position and coordinate data from the chart tooltip to determine exact placement.
 * It handles scroll position and viewport coordinates to ensure the tooltip stays aligned with the chart bars.
 */
const TooltipPortal = ({
	containerRef,
	position,
	coordinate,
	children,
}: {
	children: ReactNode;
	position: Partial<Coordinate>;
	coordinate: Partial<Coordinate>;
	containerRef: RefObject<HTMLDivElement | null>;
}) => {
	const [internalPosition, setInternalPosition] = useState<{
		x: number;
		y: number;
	} | null>(null);

	useEffect(() => {
		if (containerRef.current && position && coordinate) {
			const container = containerRef.current;
			const rect = container.getBoundingClientRect();

			// Calculate position relative to viewport and scroll
			const x =
				rect.left + (coordinate.x ?? 0) + window.scrollX - rect.width / 2;
			const y = rect.top + (position.y ?? 0) + window.scrollY;

			setInternalPosition({ x, y });
		} else {
			setInternalPosition(null);
		}
	}, [coordinate, containerRef, position]);

	if (!internalPosition) {
		return null;
	}

	return createPortal(
		<div
			style={{
				position: "absolute",
				left: 0,
				top: 0,
				transform: `translate3d(${internalPosition.x}px, ${internalPosition.y}px, 0)`,
				zIndex: 9999,
			}}
		>
			{children}
		</div>,
		document.body,
	);
};

type FlowRunTooltipProps = TooltipProps<number, string> & {
	containerRef: RefObject<HTMLDivElement | null>;
};

const FlowRunTooltip = ({
	payload,
	active,
	containerRef,
	coordinate,
	position,
}: FlowRunTooltipProps) => {
	if (!active || !payload || !payload.length || !position || !coordinate) {
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
		<TooltipPortal
			position={position}
			coordinate={coordinate}
			containerRef={containerRef}
		>
			<Card>
				<CardHeader>
					<CardTitle className="flex items-center gap-1">
						{flow && (
							<Link
								to={"/flows/flow/$id"}
								params={{ id: flow.id }}
								className="text-base font-medium"
							>
								{flow.name}
							</Link>
						)}
						<ChevronRight className="size-4" />
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
						<Link
							to={"/deployments/deployment/$id"}
							params={{ id: deployment.id }}
							className="flex items-center gap-1"
						>
							<Rocket className="size-4" />
							<p className="text-sm font-medium whitespace-nowrap">
								{deployment.name}
							</p>
						</Link>
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
		</TooltipPortal>
	);
};

FlowRunTooltip.displayName = "FlowRunTooltip";
