import type { SimpleFlowRun } from "@/api/flow-runs";
import type { components } from "@/api/prefect";
import { STATE_TYPES } from "@/components/flow-runs/flow-runs-list/flow-runs-filters/state-filter-utils";
import { secondsToApproximateString } from "@/utils/seconds";

type StateType = components["schemas"]["StateType"];
type HistoryResponse = components["schemas"]["HistoryResponse"];

/** The history endpoint returns at most this many runs, newest first. */
export const HISTORY_LIMIT = 1000;

const SECOND = 1;
const MINUTE = 60 * SECOND;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** Drawn first to last, so failures sit on top of the successes around them. */
export const STATE_DRAW_ORDER = [
	"COMPLETED",
	"CANCELLED",
	"PAUSED",
	"SCHEDULED",
	"PENDING",
	"CANCELLING",
	"RUNNING",
	"CRASHED",
	"FAILED",
] as const satisfies readonly StateType[];

/** States whose runs have not started, drawn as rings instead of dots. */
export const NOT_STARTED_STATES: ReadonlySet<StateType> = new Set([
	"SCHEDULED",
	"PENDING",
]);

/**
 * Formats a run duration. Below ten seconds it keeps the precision that
 * `secondsToApproximateString` rounds away, since most runs on a log axis
 * finish in under a second.
 */
export const formatDuration = (seconds: number): string => {
	if (!(seconds > 0)) return "0s";
	const ms = Math.round(seconds * 1000);
	if (ms < 1000) return `${Math.max(ms, 1)}ms`;
	if (seconds < 10) return `${Math.round(seconds * 10) / 10}s`;
	return secondsToApproximateString(seconds);
};

/** Gridline values for the duration axis, each a round number of its unit. */
export const DURATION_TICKS = [
	{ seconds: 0.001, label: "1ms" },
	{ seconds: 0.01, label: "10ms" },
	{ seconds: 0.1, label: "100ms" },
	{ seconds: SECOND, label: "1s" },
	{ seconds: 10 * SECOND, label: "10s" },
	{ seconds: MINUTE, label: "1m" },
	{ seconds: 10 * MINUTE, label: "10m" },
	{ seconds: HOUR, label: "1h" },
	{ seconds: 6 * HOUR, label: "6h" },
	{ seconds: DAY, label: "1d" },
	{ seconds: 7 * DAY, label: "1w" },
	{ seconds: 30 * DAY, label: "30d" },
] as const;

export type DurationTick = (typeof DURATION_TICKS)[number];

export type DurationAxis = {
	domain: [number, number];
	ticks: DurationTick[];
};

/**
 * A log-scale duration axis whose ends are gridlines, wide enough for every
 * positive duration. Zero durations are drawn in their own lane, not here.
 */
export const durationAxis = (durations: readonly number[]): DurationAxis => {
	const positive = durations.filter((duration) => duration > 0);
	if (positive.length === 0) {
		return {
			domain: [SECOND, MINUTE],
			ticks: DURATION_TICKS.filter(
				(tick) => tick.seconds >= SECOND && tick.seconds <= MINUTE,
			),
		};
	}
	const min = Math.min(...positive);
	const max = Math.max(...positive);
	let low = DURATION_TICKS.findLastIndex((tick) => tick.seconds <= min);
	let high = DURATION_TICKS.findIndex((tick) => tick.seconds >= max);
	if (low === -1) low = 0;
	if (high === -1) high = DURATION_TICKS.length - 1;
	if (low === high) {
		if (high < DURATION_TICKS.length - 1) high += 1;
		else low -= 1;
	}
	const ticks = DURATION_TICKS.slice(low, high + 1);
	return {
		domain: [
			Math.min(DURATION_TICKS[low].seconds, min),
			Math.max(DURATION_TICKS[high].seconds, max),
		],
		ticks,
	};
};

/** Keeps every nth tick so that each kept label has `minSpacing` pixels. */
export const thinTicks = <T>(
	ticks: readonly T[],
	available: number,
	minSpacing: number,
): T[] => {
	let step = 1;
	while (
		step < ticks.length - 1 &&
		available / Math.ceil(ticks.length / step) < minSpacing
	) {
		step += 1;
	}
	return ticks.filter((_, index) => index % step === 0);
};

export type TimeWindow = {
	start: number;
	end: number;
	/** Runs after the window's end, typically scheduled ones. */
	upcoming: number;
};

/**
 * The time span the plot shows. An explicit range wins. Without one the plot
 * ends now, so a run scheduled months ahead cannot squash today into a sliver;
 * runs after the end are counted instead of drawn.
 */
export const resolveTimeWindow = ({
	runs,
	startDate,
	endDate,
	now,
}: {
	runs: readonly SimpleFlowRun[];
	startDate?: Date;
	endDate?: Date;
	now: number;
}): TimeWindow => {
	const times = runs.map((run) => Date.parse(run.timestamp));
	const hasPastRuns = times.some((time) => time <= now);
	const end =
		endDate?.getTime() ??
		(hasPastRuns || times.length === 0 ? now : Math.max(...times));
	const inWindow = times.filter((time) => time <= end);
	const start =
		startDate?.getTime() ??
		(inWindow.length > 0 ? Math.min(...inWindow) : end - HOUR);
	const upcoming = times.length - inWindow.length;
	if (start >= end) {
		return { start: end - HOUR, end: end + HOUR, upcoming };
	}
	if (startDate) return { start, end, upcoming };
	return { start: start - (end - start) * 0.02, end, upcoming };
};

/**
 * When the history endpoint's row limit cut the window short, the newest runs
 * are the ones loaded, so nothing before the oldest loaded run is known.
 * Returns that boundary, or undefined when every run in the window is present.
 */
export const loadedSince = (
	runs: readonly SimpleFlowRun[],
	totalCount: number | undefined,
): number | undefined => {
	const truncated =
		totalCount === undefined
			? runs.length >= HISTORY_LIMIT
			: runs.length < totalCount;
	if (!truncated || runs.length === 0) return undefined;
	return Math.min(...runs.map((run) => Date.parse(run.timestamp)));
};

export type StateCount = { state: StateType; count: number };

export type RunsSummary = {
	total: number;
	byState: StateCount[];
	median: number | undefined;
	p90: number | undefined;
};

const quantile = (sorted: readonly number[], q: number) =>
	sorted.length === 0
		? undefined
		: sorted[Math.min(sorted.length - 1, Math.floor(q * sorted.length))];

const inLegendOrder = (counts: ReadonlyMap<StateType, number>): StateCount[] =>
	STATE_TYPES.flatMap((state) => {
		const count = counts.get(state);
		return count ? [{ state, count }] : [];
	});

export const summarizeRuns = (runs: readonly SimpleFlowRun[]): RunsSummary => {
	const counts = new Map<StateType, number>();
	for (const run of runs) {
		counts.set(run.state_type, (counts.get(run.state_type) ?? 0) + 1);
	}
	const durations = runs
		.filter((run) => run.duration > 0)
		.map((run) => run.duration)
		.sort((a, b) => a - b);
	return {
		total: runs.length,
		byState: inLegendOrder(counts),
		median: quantile(durations, 0.5),
		p90: quantile(durations, 0.9),
	};
};

/** Runs per state type, summed over every interval and state name. */
export const countRunsByState = (
	history: readonly HistoryResponse[],
): StateCount[] => {
	const counts = new Map<StateType, number>();
	for (const interval of history) {
		for (const { state_type, count_runs } of interval.states) {
			counts.set(state_type, (counts.get(state_type) ?? 0) + count_runs);
		}
	}
	return inLegendOrder(counts);
};

export type PlotPoint = {
	run: SimpleFlowRun;
	x: number;
	y: number;
};

/**
 * The closest point within `maxDistance` pixels of (x, y). Points are ordered
 * as drawn, so on a tie the one on top wins.
 */
export const findNearestPoint = (
	points: readonly PlotPoint[],
	x: number,
	y: number,
	maxDistance: number,
): PlotPoint | undefined => {
	let nearest: PlotPoint | undefined;
	let best = maxDistance * maxDistance;
	for (const point of points) {
		const distance = (point.x - x) ** 2 + (point.y - y) ** 2;
		if (distance <= best) {
			best = distance;
			nearest = point;
		}
	}
	return nearest;
};

/**
 * Formats time-axis labels by the largest boundary the tick does not sit on:
 * a tick on a day boundary shows the day, one inside a day shows the hour.
 */
export const createXAxisTickFormatter = () => {
	return (value: number): string => {
		const date = new Date(value);

		const second = new Date(date);
		second.setMilliseconds(0);
		if (second.getTime() < date.getTime()) {
			return `.${date.getMilliseconds().toString().padStart(3, "0").slice(0, 3)}`;
		}

		const minute = new Date(date);
		minute.setSeconds(0, 0);
		if (minute.getTime() < date.getTime()) {
			return `:${date.getSeconds().toString().padStart(2, "0")}`;
		}

		const hour = new Date(date);
		hour.setMinutes(0, 0, 0);
		if (hour.getTime() < date.getTime()) {
			return date.toLocaleTimeString(undefined, {
				hour: "numeric",
				minute: "2-digit",
			});
		}

		const day = new Date(date);
		day.setHours(0, 0, 0, 0);
		if (day.getTime() < date.getTime()) {
			return date.toLocaleTimeString(undefined, {
				hour: "numeric",
				hour12: true,
			});
		}

		const month = new Date(date);
		month.setDate(1);
		month.setHours(0, 0, 0, 0);
		if (month.getTime() < date.getTime()) {
			return date.toLocaleDateString(undefined, {
				weekday: "short",
				day: "numeric",
			});
		}

		const year = new Date(date);
		year.setMonth(0, 1);
		year.setHours(0, 0, 0, 0);
		if (year.getTime() < date.getTime()) {
			return date.toLocaleDateString(undefined, { month: "long" });
		}

		return date.getFullYear().toString();
	};
};
