import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { fireEvent, render, screen } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { createFakeArtifact, createFakeTaskRun } from "@/mocks";
import { TaskRunArtifacts } from "./index";

// Wraps component in test with a Tanstack router provider
const TaskRunArtifactsRouter = ({
	taskRun,
}: {
	taskRun: ReturnType<typeof createFakeTaskRun>;
}) => {
	const rootRoute = createRootRoute({
		component: () => <TaskRunArtifacts taskRun={taskRun} />,
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({
			initialEntries: ["/"],
		}),
		context: { queryClient: new QueryClient() },
	});
	return <RouterProvider router={router} />;
};

describe("TaskRunArtifacts", () => {
	const mockTaskRun = createFakeTaskRun();
	const mockArtifacts = Array.from({ length: 3 }, () =>
		createFakeArtifact({
			task_run_id: mockTaskRun.id,
			flow_run_id: mockTaskRun.flow_run_id,
		}),
	);

	beforeEach(() => {
		server.use(
			http.post(buildApiUrl("/artifacts/filter"), () => {
				return HttpResponse.json(mockArtifacts);
			}),
		);
	});

	it("renders empty state when no artifacts are present", async () => {
		server.use(
			http.post(buildApiUrl("/artifacts/filter"), () => {
				return HttpResponse.json([]);
			}),
		);

		render(<TaskRunArtifactsRouter taskRun={mockTaskRun} />, {
			wrapper: createWrapper(),
		});

		expect(
			await screen.findByText(/This task run did not produce any artifacts/),
		).toBeInTheDocument();
		expect(screen.getByRole("link", { name: /documentation/ })).toHaveAttribute(
			"href",
			"https://docs.prefect.io/v3/develop/artifacts",
		);
	});

	it("switches between grid and list views", async () => {
		render(<TaskRunArtifactsRouter taskRun={mockTaskRun} />, {
			wrapper: createWrapper(),
		});

		// Initially in grid view
		const gridButton = await screen.findByLabelText(/Grid view/i);
		const listButton = await screen.findByLabelText(/List view/i);
		const grid = await screen.findByTestId("task-run-artifacts-grid");
		expect(grid).toHaveClass("grid-cols-1 lg:grid-cols-2 xl:grid-cols-3");

		// Switch to list view
		fireEvent.click(listButton);
		expect(grid).toHaveClass("grid-cols-1");

		// Switch back to grid view
		fireEvent.click(gridButton);
		expect(grid).toHaveClass("grid-cols-1 lg:grid-cols-2 xl:grid-cols-3");
	});

	it("uses correct query parameters for fetching artifacts", async () => {
		let requestBody: unknown;
		server.use(
			http.post(buildApiUrl("/artifacts/filter"), async ({ request }) => {
				requestBody = await request.json();
				return HttpResponse.json(mockArtifacts);
			}),
		);

		render(<TaskRunArtifactsRouter taskRun={mockTaskRun} />, {
			wrapper: createWrapper(),
		});

		// Wait for the query to be made
		await screen.findByText(mockArtifacts[0].key as string);

		// Verify the query parameters
		expect(requestBody).toEqual({
			artifacts: {
				operator: "and_",
				task_run_id: {
					any_: [mockTaskRun.id],
				},
				type: {
					not_any_: ["result"],
				},
			},
			sort: "ID_DESC",
			offset: 0,
		});
	});
});
