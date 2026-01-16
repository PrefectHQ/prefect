import type { GraphItemSelection, ViewportDateRange } from "@prefecthq/graphs";
import type { CSSProperties } from "react";
import { lazy, Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";

const FlowRunGraphLazy = lazy(() =>
	import("./flow-run-graph").then((mod) => ({ default: mod.FlowRunGraph })),
);

type FlowRunGraphProps = {
	flowRunId: string;
	viewport?: ViewportDateRange;
	onViewportChange?: (viewport: ViewportDateRange) => void;
	selected?: GraphItemSelection;
	onSelectedChange?: (selected: GraphItemSelection | undefined) => void;
	fullscreen?: boolean;
	onFullscreenChange?: (fullscreen: boolean) => void;
	className?: string;
	style?: CSSProperties;
};

export function FlowRunGraph(props: FlowRunGraphProps) {
	return (
		<Suspense fallback={<Skeleton className="h-[500px] w-full" />}>
			<FlowRunGraphLazy {...props} />
		</Suspense>
	);
}

export type { GraphItemSelection, ViewportDateRange } from "@prefecthq/graphs";
