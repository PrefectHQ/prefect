import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import humanizeDuration from "humanize-duration";
import { describe, expect, it } from "vitest";
import type { components } from "@/api/prefect";
import { createFakeTaskRun } from "@/mocks";
import { RunCard } from "./run-card";

const RunCardRouter = ({
	taskRun,
}: {
	taskRun: components["schemas"]["TaskRun"];
}) => {
	const rootRoute = createRootRoute({
		component: () => <RunCard taskRun={taskRun} />,
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
		context: { queryClient: new QueryClient() },
	});

	return <RouterProvider router={router} />;
};

describe("RunCard", () => {
	it("formats API duration seconds as milliseconds", async () => {
		const estimatedRunTime = 125.123;
		const taskRun = createFakeTaskRun({
			estimated_run_time: estimatedRunTime,
		});

		render(<RunCardRouter taskRun={taskRun} />);

		await waitFor(() => {
			expect(
				screen.getByText(
					humanizeDuration(estimatedRunTime * 1000, {
						maxDecimalPoints: 3,
						units: ["s"],
					}),
				),
			).toBeVisible();
		});
	});
});
