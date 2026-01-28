import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it, vi } from "vitest";
import { createFakeFlowRun, createFakeTaskRun } from "@/mocks";
import { FlowRunGraphSelectionPanel } from "./flow-run-graph-selection-panel";

const createTestRouter = (
	selection: Parameters<typeof FlowRunGraphSelectionPanel>[0]["selection"],
	onClose: () => void,
) => {
	const rootRoute = createRootRoute();
	const indexRoute = createRoute({
		getParentRoute: () => rootRoute,
		path: "/",
		component: () => (
			<FlowRunGraphSelectionPanel selection={selection} onClose={onClose} />
		),
	});

	const router = createRouter({
		routeTree: rootRoute.addChildren([indexRoute]),
		history: createMemoryHistory({ initialEntries: ["/"] }),
		context: { queryClient: new QueryClient() },
	});

	return router;
};

describe("FlowRunGraphSelectionPanel", () => {
	describe("Task Run Selection", () => {
		it("renders task run details when selection.kind is 'task-run'", async () => {
			const taskRun = createFakeTaskRun({
				id: "task-run-123",
				name: "my-task-run",
				tags: ["tag1", "tag2"],
			});

			server.use(
				http.get(buildApiUrl("/ui/task_runs/:id"), () => {
					return HttpResponse.json(taskRun);
				}),
			);

			const onClose = vi.fn();
			const router = createTestRouter(
				{ kind: "task-run", id: "task-run-123" },
				onClose,
			);

			render(<RouterProvider router={router} />, {
				wrapper: createWrapper(),
			});

			await waitFor(() => {
				expect(screen.getByText("my-task-run")).toBeInTheDocument();
			});

			expect(screen.getByText("State")).toBeInTheDocument();
			expect(screen.getByText("Task Run ID")).toBeInTheDocument();
			expect(screen.getByText("task-run-123")).toBeInTheDocument();
			expect(screen.getByText("Duration")).toBeInTheDocument();
			expect(screen.getByText("Created")).toBeInTheDocument();
			expect(screen.getByText("Tags")).toBeInTheDocument();
			expect(screen.getByText("tag1")).toBeInTheDocument();
			expect(screen.getByText("tag2")).toBeInTheDocument();
		});

		it("links to task run detail page", async () => {
			const taskRun = createFakeTaskRun({
				id: "task-run-123",
				name: "my-task-run",
			});

			server.use(
				http.get(buildApiUrl("/ui/task_runs/:id"), () => {
					return HttpResponse.json(taskRun);
				}),
			);

			const onClose = vi.fn();
			const router = createTestRouter(
				{ kind: "task-run", id: "task-run-123" },
				onClose,
			);

			render(<RouterProvider router={router} />, {
				wrapper: createWrapper(),
			});

			await waitFor(() => {
				expect(screen.getByText("my-task-run")).toBeInTheDocument();
			});

			const link = screen.getByRole("link", { name: "my-task-run" });
			expect(link).toHaveAttribute("href", "/runs/task-run/task-run-123");
		});
	});

	describe("Flow Run Selection", () => {
		it("renders flow run details when selection.kind is 'flow-run'", async () => {
			const flowRun = createFakeFlowRun({
				id: "flow-run-456",
				name: "my-flow-run",
				tags: ["prod", "critical"],
			});

			server.use(
				http.get(buildApiUrl("/flow_runs/:id"), () => {
					return HttpResponse.json(flowRun);
				}),
			);

			const onClose = vi.fn();
			const router = createTestRouter(
				{ kind: "flow-run", id: "flow-run-456" },
				onClose,
			);

			render(<RouterProvider router={router} />, {
				wrapper: createWrapper(),
			});

			await waitFor(() => {
				expect(screen.getByText("my-flow-run")).toBeInTheDocument();
			});

			expect(screen.getByText("State")).toBeInTheDocument();
			expect(screen.getByText("Flow Run ID")).toBeInTheDocument();
			expect(screen.getByText("flow-run-456")).toBeInTheDocument();
			expect(screen.getByText("Duration")).toBeInTheDocument();
			expect(screen.getByText("Created")).toBeInTheDocument();
			expect(screen.getByText("Tags")).toBeInTheDocument();
			expect(screen.getByText("prod")).toBeInTheDocument();
			expect(screen.getByText("critical")).toBeInTheDocument();
		});

		it("links to flow run detail page", async () => {
			const flowRun = createFakeFlowRun({
				id: "flow-run-456",
				name: "my-flow-run",
			});

			server.use(
				http.get(buildApiUrl("/flow_runs/:id"), () => {
					return HttpResponse.json(flowRun);
				}),
			);

			const onClose = vi.fn();
			const router = createTestRouter(
				{ kind: "flow-run", id: "flow-run-456" },
				onClose,
			);

			render(<RouterProvider router={router} />, {
				wrapper: createWrapper(),
			});

			await waitFor(() => {
				expect(screen.getByText("my-flow-run")).toBeInTheDocument();
			});

			const link = screen.getByRole("link", { name: "my-flow-run" });
			expect(link).toHaveAttribute("href", "/runs/flow-run/flow-run-456");
		});
	});

	describe("Close Button", () => {
		it("calls onClose callback when close button is clicked", async () => {
			const user = userEvent.setup();
			const taskRun = createFakeTaskRun({
				id: "task-run-123",
				name: "my-task-run",
			});

			server.use(
				http.get(buildApiUrl("/ui/task_runs/:id"), () => {
					return HttpResponse.json(taskRun);
				}),
			);

			const onClose = vi.fn();
			const router = createTestRouter(
				{ kind: "task-run", id: "task-run-123" },
				onClose,
			);

			render(<RouterProvider router={router} />, {
				wrapper: createWrapper(),
			});

			await waitFor(() => {
				expect(
					screen.getByRole("button", { name: "Close panel" }),
				).toBeInTheDocument();
			});

			const closeButton = screen.getByRole("button", { name: "Close panel" });
			await user.click(closeButton);

			expect(onClose).toHaveBeenCalledTimes(1);
		});
	});

	describe("Non-node selections", () => {
		it("returns null for non-node selections", () => {
			const onClose = vi.fn();
			const router = createTestRouter(
				{
					kind: "artifact",
					id: "artifact-123",
				},
				onClose,
			);

			const { container } = render(<RouterProvider router={router} />, {
				wrapper: createWrapper(),
			});

			expect(container.querySelector(".absolute")).not.toBeInTheDocument();
		});
	});
});
