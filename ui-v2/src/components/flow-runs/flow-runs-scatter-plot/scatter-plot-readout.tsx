import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { formatDistanceToNowStrict } from "date-fns";
import { Calendar, ChevronRight, Clock, Hourglass } from "lucide-react";
import {
	buildGetFlowRunDetailsQuery,
	type SimpleFlowRun,
} from "@/api/flow-runs";
import { buildFLowDetailsQuery } from "@/api/flows";
import { Skeleton } from "@/components/ui/skeleton";
import { StateBadge } from "@/components/ui/state-badge";
import useDebounce from "@/hooks/use-debounce";
import {
	formatDuration,
	NOT_STARTED_STATES,
	type RunsSummary,
} from "./scatter-plot-utils";

const DETAILS_STALE_TIME = 5 * 60 * 1000;
/** Sweeping the pointer across the plot should not fetch every run it crosses. */
const DETAILS_DELAY = 150;

type ScatterPlotReadoutProps = {
	run: SimpleFlowRun | undefined;
	summary: RunsSummary;
	totalCount: number | undefined;
	/** Start of the loaded span when the row limit left older runs out. */
	loadedSince: number | undefined;
	upcoming: number;
	canZoom: boolean;
};

export const ScatterPlotReadout = ({
	run,
	summary,
	totalCount,
	loadedSince,
	upcoming,
	canZoom,
}: ScatterPlotReadoutProps) => (
	<div
		aria-live="polite"
		className="min-h-16 text-sm"
		data-testid="scatter-plot-readout"
	>
		{run ? (
			<RunReadout run={run} />
		) : (
			<SummaryReadout
				summary={summary}
				totalCount={totalCount}
				loadedSince={loadedSince}
				upcoming={upcoming}
				canZoom={canZoom}
			/>
		)}
	</div>
);

const RunReadout = ({ run }: { run: SimpleFlowRun }) => {
	const detailsId = useDebounce(run.id, DETAILS_DELAY);
	const current = detailsId === run.id;
	const { data: flowRun, isError } = useQuery({
		...buildGetFlowRunDetailsQuery(detailsId),
		staleTime: DETAILS_STALE_TIME,
	});
	const { data: flow } = useQuery({
		...buildFLowDetailsQuery(flowRun?.flow_id ?? ""),
		enabled: Boolean(flowRun?.flow_id),
		staleTime: DETAILS_STALE_TIME,
	});
	const details = current ? flowRun : undefined;
	const flowName = details && flow?.id === details.flow_id ? flow.name : null;
	const runName =
		details?.name ?? (current && isError ? run.id.slice(0, 8) : undefined);

	const start = new Date(run.timestamp);
	const notStarted = NOT_STARTED_STATES.has(run.state_type);
	const duration = notStarted
		? "not started"
		: run.state_type === "RUNNING"
			? `${formatDuration(run.duration)} so far`
			: formatDuration(run.duration);
	const when = start.toLocaleString(undefined, {
		month: "short",
		day: "numeric",
		hour: "numeric",
		minute: "2-digit",
		second: "2-digit",
	});

	return (
		<div className="flex flex-col gap-1.5">
			<div className="flex min-w-0 items-center gap-2">
				<StateBadge type={run.state_type} />
				<div className="flex min-w-0 items-center gap-1 text-muted-foreground">
					{flowName && (
						<>
							<span className="truncate font-medium text-foreground">
								{flowName}
							</span>
							<ChevronRight className="size-3 shrink-0" aria-hidden />
						</>
					)}
					{runName ? (
						<span className="truncate">{runName}</span>
					) : (
						<Skeleton className="h-4 w-32" />
					)}
				</div>
				<Link
					to="/runs/flow-run/$id"
					params={{ id: run.id }}
					className="ml-auto inline-flex h-11 shrink-0 items-center gap-0.5 rounded-md px-2 font-medium text-primary hover:underline md:h-8"
				>
					Open
					<ChevronRight className="size-4" aria-hidden />
				</Link>
			</div>
			<div className="flex flex-wrap gap-x-4 gap-y-1 text-muted-foreground tabular-nums">
				<span className="inline-flex items-center gap-1.5">
					<Clock className="size-3.5" aria-hidden />
					{duration}
				</span>
				<span className="inline-flex items-center gap-1.5">
					<Calendar className="size-3.5" aria-hidden />
					{when} ({formatDistanceToNowStrict(start, { addSuffix: true })})
				</span>
				{run.lateness >= 1 && (
					<span className="inline-flex items-center gap-1.5">
						<Hourglass className="size-3.5" aria-hidden />
						{formatDuration(run.lateness)} after scheduled start
					</span>
				)}
			</div>
		</div>
	);
};

const SummaryReadout = ({
	summary,
	totalCount,
	loadedSince,
	upcoming,
	canZoom,
}: Omit<ScatterPlotReadoutProps, "run">) => {
	const loaded = summary.total.toLocaleString();
	const headline =
		loadedSince === undefined
			? `${loaded} ${summary.total === 1 ? "run" : "runs"}`
			: `Latest ${loaded} of ${totalCount === undefined ? `more than ${loaded}` : totalCount.toLocaleString()} runs, since ${new Date(
					loadedSince,
				).toLocaleString(undefined, {
					weekday: "short",
					hour: "numeric",
					minute: "2-digit",
				})}`;
	const hints = [
		loadedSince !== undefined && "Narrow the date range to load older runs.",
		canZoom
			? "Hover or tap a run for details, or drag across the chart to zoom."
			: "Hover or tap a run for details.",
		upcoming > 0 &&
			`${upcoming.toLocaleString()} more scheduled after this window.`,
	].filter(Boolean);

	return (
		<div className="flex flex-col gap-1">
			<p className="tabular-nums">
				<span className="font-medium">{headline}</span>
				{summary.median !== undefined && summary.p90 !== undefined && (
					<span className="text-muted-foreground">
						{" "}
						· median {formatDuration(summary.median)} · p90{" "}
						{formatDuration(summary.p90)}
					</span>
				)}
			</p>
			<p className="text-muted-foreground">{hints.join(" ")}</p>
		</div>
	);
};
