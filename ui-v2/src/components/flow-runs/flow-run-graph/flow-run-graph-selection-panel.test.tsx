import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createFakeFlowRun } from "@/mocks/create-fake-flow-run";
import { createFakeTaskRun } from "@/mocks/create-fake-task-run";
import {
	FlowRunGraphSelectionPanel,
	type FlowRunGraphSelectionPanelProps,
} from "./flow-run-graph-selection-panel";

const SelectionPanelRouter = (props: FlowRunGraphSelectionPanelProps) => {
	const rootRoute = createRootRoute({
		component: () => <FlowRunGraphSelectionPanel {...props} />,
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

const renderWithProviders = (props: FlowRunGraphSelectionPanelProps) => {
	return render(<SelectionPanelRouter {...props} />, {
		wrapper: createWrapper(),
	});
};

describe("FlowRunGraphSelectionPanel", () => {
	const mockTaskRun = createFakeTaskRun({
		id: "task-run-123",
		name: "my-task-run",
		tags: ["tag1", "tag2"],
	});

	const mockFlowRun = createFakeFlowRun({
		id: "flow-run-456",
		name: "my-flow-run",
		tags: ["flow-tag1"],
	});

	beforeEach(() => {
		server.use(
			http.get(buildApiUrl("/ui/task_runs/:id"), () => {
				return HttpResponse.json(mockTaskRun);
			}),
			http.get(buildApiUrl("/flow_runs/:id"), () => {
				return HttpResponse.json(mockFlowRun);
			}),
		);
	});

	it("renders task run details when selection.kind is 'task-run'", async () => {
		const onClose = vi.fn();
		const selection = { kind: "task-run" as const, id: "task-run-123" };

		renderWithProviders({ selection, onClose });

		await waitFor(() => {
			expect(screen.getByText("my-task-run")).toBeInTheDocument();
		});

		expect(screen.getByText("Task Run ID")).toBeInTheDocument();
		expect(screen.getByText("task-run-123")).toBeInTheDocument();
		expect(screen.getByText("Duration")).toBeInTheDocument();
		expect(screen.getByText("Created")).toBeInTheDocument();
	});

	it("renders flow run details when selection.kind is 'flow-run'", async () => {
		const onClose = vi.fn();
		const selection = { kind: "flow-run" as const, id: "flow-run-456" };

		renderWithProviders({ selection, onClose });

		await waitFor(() => {
			expect(screen.getByText("my-flow-run")).toBeInTheDocument();
		});

		expect(screen.getByText("Flow Run ID")).toBeInTheDocument();
		expect(screen.getByText("flow-run-456")).toBeInTheDocument();
		expect(screen.getByText("Duration")).toBeInTheDocument();
		expect(screen.getByText("Created")).toBeInTheDocument();
	});

	it("calls onClose when close button is clicked", async () => {
		const user = userEvent.setup();
		const onClose = vi.fn();
		const selection = { kind: "task-run" as const, id: "task-run-123" };

		renderWithProviders({ selection, onClose });

		await waitFor(() => {
			expect(screen.getByText("my-task-run")).toBeInTheDocument();
		});

		const closeButton = screen.getByRole("button", { name: /close panel/i });
		await user.click(closeButton);

		expect(onClose).toHaveBeenCalledTimes(1);
	});

	it("renders link to task run detail page", async () => {
		const onClose = vi.fn();
		const selection = { kind: "task-run" as const, id: "task-run-123" };

		renderWithProviders({ selection, onClose });

		await waitFor(() => {
			expect(screen.getByText("my-task-run")).toBeInTheDocument();
		});

		const link = screen.getByRole("link", { name: "my-task-run" });
		expect(link).toHaveAttribute("href", "/runs/task-run/task-run-123");
	});

	it("renders link to flow run detail page", async () => {
		const onClose = vi.fn();
		const selection = { kind: "flow-run" as const, id: "flow-run-456" };

		renderWithProviders({ selection, onClose });

		await waitFor(() => {
			expect(screen.getByText("my-flow-run")).toBeInTheDocument();
		});

		const link = screen.getByRole("link", { name: "my-flow-run" });
		expect(link).toHaveAttribute("href", "/runs/flow-run/flow-run-456");
	});

	it("returns null for non-node selections", () => {
		const onClose = vi.fn();
		const selection = {
			kind: "artifact" as const,
			id: "artifact-123",
		};

		const { container } = renderWithProviders({ selection, onClose });

		expect(container.firstChild).toBeNull();
	});

	it("displays tags when present", async () => {
		const onClose = vi.fn();
		const selection = { kind: "task-run" as const, id: "task-run-123" };

		renderWithProviders({ selection, onClose });

		await waitFor(() => {
			expect(screen.getByText("my-task-run")).toBeInTheDocument();
		});

		expect(screen.getByText("Tags")).toBeInTheDocument();
	});
});
