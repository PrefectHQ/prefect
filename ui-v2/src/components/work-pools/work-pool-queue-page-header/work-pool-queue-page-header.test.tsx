import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, waitFor } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it, vi } from "vitest";
import type { WorkPoolQueue } from "@/api/work-pool-queues";
import { createFakeWorkPoolQueue } from "@/mocks";
import {
	WorkPoolQueuePageHeader,
	type WorkPoolQueuePageHeaderProps,
} from "./work-pool-queue-page-header";

// Mock the sub-components that have network behavior
vi.mock("@/components/work-pools/work-pool-queue-toggle", () => ({
	WorkPoolQueueToggle: ({ queue }: { queue: WorkPoolQueue }) => (
		<div data-testid="work-pool-queue-toggle">Toggle for {queue.name}</div>
	),
}));

vi.mock("@/components/work-pools/work-pool-queue-menu", () => ({
	WorkPoolQueueMenu: ({ queue }: { queue: WorkPoolQueue }) => (
		<div data-testid="work-pool-queue-menu">Menu for {queue.name}</div>
	),
}));

// Wraps component in test with a TanStack router provider
const WorkPoolQueuePageHeaderRouter = (props: WorkPoolQueuePageHeaderProps) => {
	const rootRoute = createRootRoute({
		component: () => <WorkPoolQueuePageHeader {...props} />,
	});

	// Define routes that the breadcrumb links point to
	const workPoolsRoute = createRoute({
		getParentRoute: () => rootRoute,
		path: "/work-pools",
		component: () => <div>Work Pools Page</div>,
	});

	const workPoolDetailRoute = createRoute({
		getParentRoute: () => rootRoute,
		path: "/work-pools/work-pool/$workPoolName",
		component: () => <div>Work Pool Detail Page</div>,
	});

	const routeTree = rootRoute.addChildren([
		workPoolsRoute,
		workPoolDetailRoute,
	]);

	const router = createRouter({
		routeTree,
		history: createMemoryHistory({
			initialEntries: ["/"],
		}),
		context: { queryClient: new QueryClient() },
	});

	return <RouterProvider router={router} />;
};

const mockQueue = createFakeWorkPoolQueue({
	name: "test-queue",
	work_pool_name: "test-work-pool",
	status: "READY",
});

describe("WorkPoolQueuePageHeader", () => {
	it("renders breadcrumbs correctly", async () => {
		const { getByText, getByRole } = await waitFor(() =>
			render(
				<WorkPoolQueuePageHeaderRouter
					workPoolName="test-work-pool"
					queue={mockQueue}
				/>,
				{
					wrapper: createWrapper(),
				},
			),
		);

		expect(getByText("Work Pools")).toBeTruthy();
		expect(getByText("test-work-pool")).toBeTruthy();
		// Check that the queue name appears in the breadcrumb
		const breadcrumb = getByRole("navigation", { name: /breadcrumb/i });
		expect(breadcrumb).toHaveTextContent(mockQueue.name);
	});

	it("displays queue name in breadcrumb", async () => {
		const { getByText } = await waitFor(() =>
			render(
				<WorkPoolQueuePageHeaderRouter
					workPoolName="test-work-pool"
					queue={mockQueue}
				/>,
				{
					wrapper: createWrapper(),
				},
			),
		);

		// Check the queue name appears in the breadcrumb page
		expect(getByText(mockQueue.name)).toBeTruthy();
	});

	it("shows actions components", async () => {
		const { getByTestId } = await waitFor(() =>
			render(
				<WorkPoolQueuePageHeaderRouter
					workPoolName="test-work-pool"
					queue={mockQueue}
				/>,
				{
					wrapper: createWrapper(),
				},
			),
		);

		expect(getByTestId("work-pool-queue-toggle")).toBeTruthy();
		expect(getByTestId("work-pool-queue-menu")).toBeTruthy();
	});

	it("passes onUpdate callback to actions", async () => {
		const onUpdate = vi.fn();
		const { getByTestId } = await waitFor(() =>
			render(
				<WorkPoolQueuePageHeaderRouter
					workPoolName="test-work-pool"
					queue={mockQueue}
					onUpdate={onUpdate}
				/>,
				{
					wrapper: createWrapper(),
				},
			),
		);

		expect(getByTestId("work-pool-queue-toggle")).toBeTruthy();
		expect(getByTestId("work-pool-queue-menu")).toBeTruthy();
	});

	it("applies custom className", async () => {
		const { container } = await waitFor(() =>
			render(
				<WorkPoolQueuePageHeaderRouter
					workPoolName="test-work-pool"
					queue={mockQueue}
					className="custom-class"
				/>,
				{
					wrapper: createWrapper(),
				},
			),
		);

		expect(container.querySelector(".custom-class")).toBeTruthy();
	});

	it("renders correct breadcrumb links", async () => {
		const { getByText } = await waitFor(() =>
			render(
				<WorkPoolQueuePageHeaderRouter
					workPoolName="my-pool"
					queue={createFakeWorkPoolQueue({
						name: "my-queue",
						work_pool_name: "my-pool",
					})}
				/>,
				{
					wrapper: createWrapper(),
				},
			),
		);

		// Check the Work Pools link
		const workPoolsLink = getByText("Work Pools").closest("a");
		expect(workPoolsLink).toHaveAttribute("href", "/work-pools");

		// Check the work pool name link
		const workPoolLink = getByText("my-pool").closest("a");
		expect(workPoolLink).toHaveAttribute(
			"href",
			"/work-pools/work-pool/my-pool",
		);
	});
});
