import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
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
	it("displays the duration in hours and minutes", async () => {
		const taskRun = createFakeTaskRun({
			estimated_run_time: 42787.67,
		});

		render(<RunCardRouter taskRun={taskRun} />);

		await waitFor(() => {
			expect(screen.getByText("11h 53m")).toBeVisible();
		});
	});
});
