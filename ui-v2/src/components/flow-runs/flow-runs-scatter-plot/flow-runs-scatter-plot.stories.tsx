import type { Meta, StoryObj } from "@storybook/react";
import type { ComponentProps } from "react";
import { fn } from "storybook/test";
import type { SimpleFlowRun } from "@/api/flow-runs";
import type { components } from "@/api/prefect";
import { createFakeSimpleFlowRunsMultiDay } from "@/mocks";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { FlowRunsScatterPlot } from ".";

const HOUR = 60 * 60 * 1000;
const NOW = Date.now();

/** A deterministic generator, so a story looks the same on every load. */
const seeded = (seed: number) => {
	let state = seed;
	return () => {
		state = (state + 0x6d2b79f5) | 0;
		let t = Math.imul(state ^ (state >>> 15), 1 | state);
		t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
};

/**
 * Runs shaped like a busy server: mostly sub-minute successes, a tail of
 * long jobs, and crashes that never recorded a duration.
 */
const busyServer = (count: number, spanHours: number, seed = 7) => {
	const random = seeded(seed);
	return Array.from({ length: count }, (_, index): SimpleFlowRun => {
		const roll = random();
		const state: components["schemas"]["StateType"] =
			roll < 0.035
				? "CRASHED"
				: roll < 0.045
					? "FAILED"
					: roll < 0.048
						? "CANCELLED"
						: "COMPLETED";
		const tail = random();
		const duration =
			state === "CRASHED" || state === "CANCELLED"
				? 0
				: tail > 0.99
					? 1800 + random() * 12_000
					: tail > 0.9
						? 20 + random() * 600
						: 0.05 + random() ** 2 * 20;
		return {
			id: `run-${seed}-${index}`,
			state_type: state,
			timestamp: new Date(NOW - random() * spanHours * HOUR).toISOString(),
			duration,
			lateness: random() > 0.95 ? random() * 300 : 0,
		};
	});
};

const scheduledAhead = (count: number): SimpleFlowRun[] =>
	Array.from({ length: count }, (_, index) => ({
		id: `scheduled-${index}`,
		state_type: "SCHEDULED",
		timestamp: new Date(NOW + (index + 1) * 6 * HOUR).toISOString(),
		duration: 0,
		lateness: 0,
	}));

export default {
	title: "Components/FlowRuns/FlowRunsScatterPlot",
	component: FlowRunsScatterPlot,
	parameters: { layout: "padded" },
	args: {
		history: busyServer(300, 24),
		startDate: new Date(NOW - 24 * HOUR),
		endDate: new Date(NOW),
		totalCount: 300,
		onRangeChange: fn(),
		selectedStateTypes: new Set(),
		onSelectedStateTypesChange: fn(),
	},
	decorators: [reactQueryDecorator, routerDecorator],
	render: function Render(args: ComponentProps<typeof FlowRunsScatterPlot>) {
		return (
			<div className="max-w-4xl">
				<FlowRunsScatterPlot {...args} />
			</div>
		);
	},
} satisfies Meta<typeof FlowRunsScatterPlot>;

type Story = StoryObj<typeof FlowRunsScatterPlot>;

export const Day: Story = {};

/**
 * Seven days requested, but the history endpoint returns only the newest
 * 1,000 of 7,432 runs; the span it could not load is marked.
 */
export const RowLimitReached: Story = {
	args: {
		history: busyServer(1000, 18),
		startDate: new Date(NOW - 7 * 24 * HOUR),
		endDate: new Date(NOW),
		totalCount: 7432,
	},
};

/** No range selected: the plot ends now and counts runs scheduled later. */
export const OpenEndedWithScheduledRuns: Story = {
	args: {
		history: [...busyServer(120, 30, 11), ...scheduledAhead(24)],
		startDate: undefined,
		endDate: undefined,
		totalCount: 144,
	},
};

/** A range reaching into the future shows scheduled runs as rings. */
export const RangeIncludingFuture: Story = {
	args: {
		history: [...busyServer(80, 12, 3), ...scheduledAhead(2)],
		startDate: new Date(NOW - 12 * HOUR),
		endDate: new Date(NOW + 12 * HOUR),
		totalCount: 82,
	},
};

export const WeekLong: Story = {
	args: {
		history: createFakeSimpleFlowRunsMultiDay(50, 7),
		startDate: new Date(NOW - 7 * 24 * HOUR),
		endDate: new Date(NOW),
		totalCount: undefined,
	},
};

export const Loading: Story = { args: { history: undefined } };

export const Empty: Story = { args: { history: [], totalCount: 0 } };

export const Phone: Story = {
	args: RowLimitReached.args,
	render: function Render(args: ComponentProps<typeof FlowRunsScatterPlot>) {
		return (
			<div className="w-[343px]">
				<FlowRunsScatterPlot {...args} />
			</div>
		);
	},
};
