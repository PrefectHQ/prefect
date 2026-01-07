import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { delay, HttpResponse, http } from "msw";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { TaskRunsCard } from "./index";

const now = new Date();
const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);

const createMockHandlers = (options?: {
	total?: number;
	completed?: number;
	failed?: number;
	running?: number;
}) => {
	const {
		total = 150,
		completed = 120,
		failed = 10,
		running = 5,
	} = options ?? {};

	return [
		http.post(buildApiUrl("/task_runs/count"), async ({ request }) => {
			const body = (await request.json()) as Record<string, unknown>;
			const taskRunsFilter = body.task_runs as Record<string, unknown>;
			const stateFilter = taskRunsFilter?.state as Record<string, unknown>;
			const stateType = stateFilter?.type as Record<string, string[]>;

			// Return different counts based on state type filter
			if (stateType?.any_?.includes("RUNNING") && stateType.any_.length === 1) {
				return HttpResponse.json(running);
			}
			if (
				stateType?.any_?.includes("FAILED") ||
				stateType?.any_?.includes("CRASHED")
			) {
				if (
					!stateType.any_.includes("COMPLETED") &&
					!stateType.any_.includes("RUNNING")
				) {
					return HttpResponse.json(failed);
				}
			}
			if (
				stateType?.any_?.includes("COMPLETED") &&
				stateType.any_.length === 1
			) {
				return HttpResponse.json(completed);
			}

			// Total (COMPLETED, FAILED, CRASHED, RUNNING)
			return HttpResponse.json(total);
		}),
		// Task runs history for trends chart
		http.post(buildApiUrl("/task_runs/history"), () => {
			return HttpResponse.json([]);
		}),
	];
};

const meta = {
	title: "Components/Dashboard/TaskRunsCard",
	component: TaskRunsCard,
	decorators: [reactQueryDecorator, routerDecorator],
	args: {
		filter: {
			startDate: sevenDaysAgo.toISOString(),
			endDate: now.toISOString(),
		},
	},
	parameters: {
		msw: {
			handlers: createMockHandlers(),
		},
	},
} satisfies Meta<typeof TaskRunsCard>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const WithRunningTasks: Story = {
	parameters: {
		msw: {
			handlers: createMockHandlers({
				total: 200,
				completed: 150,
				failed: 15,
				running: 20,
			}),
		},
	},
};

export const WithFailures: Story = {
	parameters: {
		msw: {
			handlers: createMockHandlers({
				total: 100,
				completed: 70,
				failed: 25,
				running: 0,
			}),
		},
	},
};

export const NoTasks: Story = {
	parameters: {
		msw: {
			handlers: createMockHandlers({
				total: 0,
				completed: 0,
				failed: 0,
				running: 0,
			}),
		},
	},
};

export const Loading: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/task_runs/count"), async () => {
					await delay("infinite");
					return HttpResponse.json(0);
				}),
				http.post(buildApiUrl("/task_runs/history"), async () => {
					await delay("infinite");
					return HttpResponse.json([]);
				}),
			],
		},
	},
};

export const WithError: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/task_runs/count"), () => {
					return HttpResponse.json(
						{ detail: "Internal server error" },
						{ status: 500 },
					);
				}),
				http.post(buildApiUrl("/task_runs/history"), () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
};
