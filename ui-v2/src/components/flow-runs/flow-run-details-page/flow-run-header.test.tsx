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
import { createWrapper } from "@tests/utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { createFakeFlowRun, createFakeState } from "@/mocks";
import { FlowRunHeader } from "./flow-run-header";

describe("FlowRunHeader", () => {
	const mockFlowRun = createFakeFlowRun({
		id: "test-flow-run-id",
		name: "test-flow-run",
		state_type: "COMPLETED",
		state_name: "Completed",
		state: createFakeState({
			type: "COMPLETED",
			name: "Completed",
		}),
	});

	const mockOnDeleteClick = vi.fn();

	const renderFlowRunHeader = (props = {}) => {
		const rootRoute = createRootRoute({
			component: () => (
				<>
					<Toaster />
					<FlowRunHeader
						flowRun={mockFlowRun}
						onDeleteClick={mockOnDeleteClick}
						{...props}
					/>
				</>
			),
		});

		const runsRoute = createRoute({
			path: "/runs",
			getParentRoute: () => rootRoute,
			component: () => <div>Runs Page</div>,
		});

		const routeTree = rootRoute.addChildren([runsRoute]);

		const router = createRouter({
			routeTree,
			history: createMemoryHistory({
				initialEntries: ["/"],
			}),
			context: {
				queryClient: new QueryClient(),
			},
		});

		return render(<RouterProvider router={router} />, {
			wrapper: createWrapper(),
		});
	};

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders breadcrumb with Runs link and flow run name", async () => {
		renderFlowRunHeader();

		await waitFor(() => {
			expect(screen.getByText("Runs")).toBeInTheDocument();
		});

		const nav = screen.getByRole("navigation");
		expect(nav).toHaveTextContent("Runs");
		expect(nav).toHaveTextContent("test-flow-run");
	});

	it("renders the Runs breadcrumb link with correct navigation", async () => {
		renderFlowRunHeader();

		await waitFor(() => {
			expect(screen.getByText("Runs")).toBeInTheDocument();
		});

		const runsLink = screen.getByRole("link", { name: "Runs" });
		expect(runsLink).toHaveAttribute("href", "/runs");
	});

	it("displays the flow run state badge", async () => {
		renderFlowRunHeader();

		await waitFor(() => {
			expect(screen.getByText("Completed")).toBeInTheDocument();
		});
	});

	it("copies flow run ID to clipboard and shows success toast", async () => {
		renderFlowRunHeader();
		const user = userEvent.setup();

		await waitFor(() => {
			expect(screen.getByText("test-flow-run")).toBeInTheDocument();
		});

		const moreButton = screen.getByRole("button", { expanded: false });
		await user.click(moreButton);

		await waitFor(() => {
			expect(screen.getByText("Copy ID")).toBeInTheDocument();
		});
		await user.click(screen.getByText("Copy ID"));

		expect(await navigator.clipboard.readText()).toBe(mockFlowRun.id);

		await waitFor(() => {
			expect(
				screen.getByText("Copied flow run ID to clipboard"),
			).toBeInTheDocument();
		});
	});

	it("opens delete confirmation dialog when Delete is clicked", async () => {
		renderFlowRunHeader();
		const user = userEvent.setup();

		await waitFor(() => {
			expect(screen.getByText("test-flow-run")).toBeInTheDocument();
		});

		const moreButton = screen.getByRole("button", { expanded: false });
		await user.click(moreButton);

		await waitFor(() => {
			expect(screen.getByText("Delete")).toBeInTheDocument();
		});
		await user.click(screen.getByText("Delete"));

		await waitFor(() => {
			expect(screen.getByText("Delete Flow Run")).toBeInTheDocument();
			expect(
				screen.getByText(
					`Are you sure you want to delete flow run ${mockFlowRun.name}?`,
				),
			).toBeInTheDocument();
		});
	});

	it("calls onDeleteClick when delete is confirmed", async () => {
		renderFlowRunHeader();
		const user = userEvent.setup();

		await waitFor(() => {
			expect(screen.getByText("test-flow-run")).toBeInTheDocument();
		});

		const moreButton = screen.getByRole("button", { expanded: false });
		await user.click(moreButton);

		await waitFor(() => {
			expect(screen.getByText("Delete")).toBeInTheDocument();
		});
		await user.click(screen.getByText("Delete"));

		await waitFor(() => {
			expect(screen.getByText("Delete Flow Run")).toBeInTheDocument();
		});

		await user.click(screen.getByRole("button", { name: /Delete/i }));

		await waitFor(() => {
			expect(mockOnDeleteClick).toHaveBeenCalledTimes(1);
		});
	});

	it("renders with different flow run states", async () => {
		const failedFlowRun = createFakeFlowRun({
			id: "failed-flow-run-id",
			name: "failed-flow-run",
			state_type: "FAILED",
			state_name: "Failed",
			state: createFakeState({
				type: "FAILED",
				name: "Failed",
			}),
		});

		const rootRoute = createRootRoute({
			component: () => (
				<>
					<Toaster />
					<FlowRunHeader
						flowRun={failedFlowRun}
						onDeleteClick={mockOnDeleteClick}
					/>
				</>
			),
		});

		const router = createRouter({
			routeTree: rootRoute,
			history: createMemoryHistory({
				initialEntries: ["/"],
			}),
			context: {
				queryClient: new QueryClient(),
			},
		});

		render(<RouterProvider router={router} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Failed")).toBeInTheDocument();
		});
	});
});
