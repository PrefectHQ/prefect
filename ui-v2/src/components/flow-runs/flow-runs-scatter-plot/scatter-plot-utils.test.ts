import { describe, expect, it } from "vitest";
import { createFakeSimpleFlowRun } from "@/mocks";
import {
	createXAxisTickFormatter,
	durationAxis,
	findNearestPoint,
	formatDuration,
	HISTORY_LIMIT,
	loadedSince,
	resolveTimeWindow,
	summarizeRuns,
	thinTicks,
} from "./scatter-plot-utils";

const HOUR = 60 * 60 * 1000;
const NOW = Date.parse("2026-11-06T12:00:00Z");
const at = (offsetHours: number) => new Date(NOW + offsetHours * HOUR);
const runAt = (offsetHours: number, duration = 1) =>
	createFakeSimpleFlowRun({
		timestamp: at(offsetHours).toISOString(),
		duration,
	});

describe("formatDuration", () => {
	it.each([
		[0, "0s"],
		[-1, "0s"],
		[0.0004, "1ms"],
		[0.563, "563ms"],
		[0.9996, "1s"],
		[1.818, "1.8s"],
		[9.96, "10s"],
		[119, "1m 59s"],
	])("formats %s seconds as %s", (seconds, expected) => {
		expect(formatDuration(seconds)).toBe(expected);
	});
});

describe("durationAxis", () => {
	it("bounds the durations with gridlines on either side", () => {
		const axis = durationAxis([0.02, 1.8, 22, 571, 12600]);

		expect(axis.ticks.map((tick) => tick.label)).toEqual([
			"10ms",
			"100ms",
			"1s",
			"10s",
			"1m",
			"10m",
			"1h",
			"6h",
		]);
		expect(axis.domain).toEqual([0.01, 6 * 60 * 60]);
	});

	it("ignores zero durations, which are drawn in their own lane", () => {
		expect(durationAxis([0, 0, 5]).ticks.map((tick) => tick.label)).toEqual([
			"1s",
			"10s",
		]);
	});

	it("spans two gridlines when every duration sits on one", () => {
		expect(durationAxis([60, 60]).ticks.map((tick) => tick.label)).toEqual([
			"1m",
			"10m",
		]);
	});

	it("falls back to seconds and minutes without positive durations", () => {
		expect(durationAxis([0]).domain).toEqual([1, 60]);
	});

	it("extends past the outermost gridlines for extreme durations", () => {
		const axis = durationAxis([0.0001, 90 * 24 * 60 * 60]);

		expect(axis.domain).toEqual([0.0001, 90 * 24 * 60 * 60]);
	});
});

describe("thinTicks", () => {
	it("keeps every tick when they fit", () => {
		expect(thinTicks([1, 2, 3, 4], 200, 22)).toEqual([1, 2, 3, 4]);
	});

	it("drops alternate ticks until labels have room", () => {
		expect(thinTicks([1, 2, 3, 4, 5, 6, 7, 8], 100, 22)).toEqual([1, 3, 5, 7]);
	});
});

describe("resolveTimeWindow", () => {
	it("uses an explicit range as given", () => {
		const window = resolveTimeWindow({
			runs: [runAt(-1)],
			startDate: at(-24),
			endDate: at(0),
			now: NOW,
		});

		expect(window).toEqual({
			start: at(-24).getTime(),
			end: NOW,
			upcoming: 0,
		});
	});

	it("ends at now instead of at runs scheduled months ahead", () => {
		const window = resolveTimeWindow({
			runs: [runAt(-48), runAt(-1), runAt(24 * 90, 0), runAt(24 * 91, 0)],
			now: NOW,
		});

		expect(window.end).toBe(NOW);
		expect(window.upcoming).toBe(2);
		expect(window.start).toBeLessThan(at(-48).getTime());
	});

	it("shows future runs when every run is in the future", () => {
		const window = resolveTimeWindow({
			runs: [runAt(1, 0), runAt(5, 0)],
			now: NOW,
		});

		expect(window.end).toBe(at(5).getTime());
		expect(window.upcoming).toBe(0);
	});

	it("opens a window around a single run", () => {
		const window = resolveTimeWindow({ runs: [runAt(0)], now: NOW });

		expect(window.start).toBeLessThan(NOW);
		expect(window.end).toBeGreaterThan(NOW);
	});
});

describe("loadedSince", () => {
	const runs = [runAt(-1), runAt(-3), runAt(-2)];

	it("returns the oldest loaded run when the count says more exist", () => {
		expect(loadedSince(runs, 7432)).toBe(at(-3).getTime());
	});

	it("returns undefined when every matching run was loaded", () => {
		expect(loadedSince(runs, 3)).toBeUndefined();
	});

	it("assumes a cut when a full page arrives without a count", () => {
		const fullPage = Array.from({ length: HISTORY_LIMIT }, (_, index) =>
			runAt(-index / 10),
		);

		expect(loadedSince(fullPage, undefined)).toBe(
			at(-(HISTORY_LIMIT - 1) / 10).getTime(),
		);
		expect(loadedSince(runs, undefined)).toBeUndefined();
	});
});

describe("summarizeRuns", () => {
	it("counts states in the state filter order and takes duration quantiles", () => {
		const summary = summarizeRuns([
			createFakeSimpleFlowRun({ state_type: "CRASHED", duration: 0 }),
			createFakeSimpleFlowRun({ state_type: "COMPLETED", duration: 1 }),
			createFakeSimpleFlowRun({ state_type: "COMPLETED", duration: 2 }),
			createFakeSimpleFlowRun({ state_type: "FAILED", duration: 30 }),
		]);

		expect(summary.total).toBe(4);
		expect(summary.byState).toEqual([
			{ state: "COMPLETED", count: 2 },
			{ state: "FAILED", count: 1 },
			{ state: "CRASHED", count: 1 },
		]);
		expect(summary.median).toBe(2);
		expect(summary.p90).toBe(30);
	});

	it("leaves quantiles undefined when nothing has run", () => {
		const summary = summarizeRuns([
			createFakeSimpleFlowRun({ state_type: "SCHEDULED", duration: 0 }),
		]);

		expect(summary.median).toBeUndefined();
	});
});

describe("findNearestPoint", () => {
	const point = (x: number, y: number) => ({
		run: createFakeSimpleFlowRun(),
		x,
		y,
	});

	it("finds the closest point within the radius", () => {
		const near = point(10, 10);

		expect(findNearestPoint([point(40, 40), near], 12, 12, 12)).toBe(near);
	});

	it("ignores points beyond the radius", () => {
		expect(findNearestPoint([point(40, 40)], 0, 0, 12)).toBeUndefined();
	});

	it("prefers the point drawn last on a tie", () => {
		const below = point(10, 10);
		const above = point(10, 10);

		expect(findNearestPoint([below, above], 10, 10, 12)).toBe(above);
	});
});

describe("createXAxisTickFormatter", () => {
	const formatter = createXAxisTickFormatter();

	it("formats milliseconds when crossing millisecond boundary", () => {
		const date = new Date("2024-01-15T12:30:45.123Z");
		expect(formatter(date.getTime())).toBe(".123");
	});

	it("formats seconds when crossing second boundary", () => {
		const date = new Date("2024-01-15T12:30:45.000Z");
		expect(formatter(date.getTime())).toBe(":45");
	});

	it("formats hour:minute when crossing minute boundary", () => {
		const date = new Date("2024-01-15T12:30:00.000Z");
		expect(formatter(date.getTime())).toMatch(/12:30|30/);
	});

	it("formats hour when crossing hour boundary", () => {
		const date = new Date("2024-01-15T12:00:00.000Z");
		expect(formatter(date.getTime())).toMatch(/12|PM|AM|noon/i);
	});

	it("formats weekday and day when crossing day boundary", () => {
		const date = new Date("2024-01-15T00:00:00.000Z");
		expect(formatter(date.getTime())).toMatch(/Mon|15|Jan/i);
	});

	it("formats month when crossing month boundary", () => {
		const date = new Date("2024-06-01T00:00:00.000Z");
		expect(formatter(date.getTime())).toMatch(/June|Jun|Sat|1/i);
	});

	it("formats year when crossing year boundary", () => {
		const date = new Date("2024-01-01T00:00:00.000Z");
		expect(formatter(date.getTime())).toMatch(/2024|January|Jan|Mon|1/i);
	});
});
