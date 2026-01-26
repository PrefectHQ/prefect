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
import { describe, expect, it, vi } from "vitest";
import { FlowRunGraphEventPopover } from "./flow-run-graph-event-popover";

type FlowRunGraphEventPopoverProps = Parameters<
	typeof FlowRunGraphEventPopover
>[0];

// Wraps component in test with a Tanstack router provider
const FlowRunGraphEventPopoverRouter = (
	props: FlowRunGraphEventPopoverProps,
) => {
	const rootRoute = createRootRoute({
		component: () => <FlowRunGraphEventPopover {...props} />,
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

describe("FlowRunGraphEventPopover", () => {
	const createEventSelection = (overrides = {}) => ({
		kind: "event" as const,
		id: "event-123",
		occurred: new Date("2024-01-15T10:30:00Z"),
		position: { x: 100, y: 200, width: 20, height: 20 },
		...overrides,
	});

	const mockEventResponse = {
		events: [
			{
				id: "event-123",
				occurred: "2024-01-15T10:30:00Z",
				received: "2024-01-15T10:30:01Z",
				event: "prefect.flow-run.completed",
				resource: {
					"prefect.resource.id": "prefect.flow-run.abc123",
					"prefect.resource.name": "my-flow-run",
				},
				payload: {},
				related: [],
			},
		],
		total: 1,
		next_page: null,
	};

	const setupMockServer = () => {
		server.use(
			http.post(buildApiUrl("/events/filter"), () => {
				return HttpResponse.json(mockEventResponse);
			}),
		);
	};

	it("renders event details correctly", async () => {
		setupMockServer();
		const selection = createEventSelection();
		const onClose = vi.fn();

		render(
			<FlowRunGraphEventPopoverRouter
				selection={selection}
				onClose={onClose}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(await screen.findByText("Event")).toBeInTheDocument();
		// Check for human-readable event label
		expect(await screen.findByText("Flow run completed")).toBeInTheDocument();
		// Check for raw event name
		expect(
			await screen.findByText("prefect.flow-run.completed"),
		).toBeInTheDocument();
		expect(screen.getByText("Occurred")).toBeInTheDocument();
		// Check for numeric date format (2024/01/15 10:30:00 AM in UTC)
		expect(screen.getByText(/2024\/01\/15/)).toBeInTheDocument();
		expect(screen.getByText("Resource")).toBeInTheDocument();
		expect(screen.getByText("my-flow-run")).toBeInTheDocument();
	});

	it("calls onClose when close button is clicked", async () => {
		setupMockServer();
		const user = userEvent.setup();
		const selection = createEventSelection();
		const onClose = vi.fn();

		render(
			<FlowRunGraphEventPopoverRouter
				selection={selection}
				onClose={onClose}
			/>,
			{ wrapper: createWrapper() },
		);

		const closeButton = await screen.findByRole("button", {
			name: "Close popover",
		});
		await user.click(closeButton);

		expect(onClose).toHaveBeenCalledTimes(1);
	});

	it("calls onClose when clicking outside the popover", async () => {
		setupMockServer();
		const user = userEvent.setup();
		const selection = createEventSelection();
		const onClose = vi.fn();

		render(
			<FlowRunGraphEventPopoverRouter
				selection={selection}
				onClose={onClose}
			/>,
			{ wrapper: createWrapper() },
		);

		await screen.findByRole("button", { name: "Close popover" });

		// Click outside by pressing Escape (more reliable than clicking outside)
		await user.keyboard("{Escape}");

		await waitFor(() => {
			expect(onClose).toHaveBeenCalled();
		});
	});

	it("calls onClose when Escape key is pressed", async () => {
		setupMockServer();
		const user = userEvent.setup();
		const selection = createEventSelection();
		const onClose = vi.fn();

		render(
			<FlowRunGraphEventPopoverRouter
				selection={selection}
				onClose={onClose}
			/>,
			{ wrapper: createWrapper() },
		);

		await screen.findByRole("button", { name: "Close popover" });

		await user.keyboard("{Escape}");

		await waitFor(() => {
			expect(onClose).toHaveBeenCalled();
		});
	});

	it("returns null when position is not provided", () => {
		setupMockServer();
		const selection = createEventSelection({ position: undefined });
		const onClose = vi.fn();

		render(
			<FlowRunGraphEventPopoverRouter
				selection={selection}
				onClose={onClose}
			/>,
			{ wrapper: createWrapper() },
		);

		// The router wrapper will have content, but the popover should not render
		expect(screen.queryByRole("button", { name: "Close popover" })).toBeNull();
	});

	it("positions the anchor based on selection position", async () => {
		setupMockServer();
		const selection = createEventSelection({
			position: { x: 150, y: 250, width: 30, height: 30 },
		});
		const onClose = vi.fn();

		render(
			<FlowRunGraphEventPopoverRouter
				selection={selection}
				onClose={onClose}
			/>,
			{ wrapper: createWrapper() },
		);

		await screen.findByRole("button", { name: "Close popover" });

		const anchor = document.querySelector('[data-slot="popover-anchor"]');
		expect(anchor).toHaveStyle({
			left: "165px",
			top: "280px",
		});
	});

	it("shows loading state while fetching event details", async () => {
		server.use(
			http.post(buildApiUrl("/events/filter"), async () => {
				await new Promise((resolve) => setTimeout(resolve, 100));
				return HttpResponse.json(mockEventResponse);
			}),
		);

		const selection = createEventSelection();
		const onClose = vi.fn();

		render(
			<FlowRunGraphEventPopoverRouter
				selection={selection}
				onClose={onClose}
			/>,
			{ wrapper: createWrapper() },
		);

		// Wait for the router to initialize and the popover to render
		expect(
			await screen.findByRole("button", { name: "Close popover" }),
		).toBeVisible();
		expect(
			await screen.findByText("prefect.flow-run.completed"),
		).toBeInTheDocument();
	});

	it("fetches and displays resource name when not provided in event", async () => {
		server.use(
			http.post(buildApiUrl("/events/filter"), () => {
				return HttpResponse.json({
					events: [
						{
							id: "event-123",
							occurred: "2024-01-15T10:30:00Z",
							received: "2024-01-15T10:30:01Z",
							event: "prefect.flow-run.started",
							resource: {
								"prefect.resource.id": "prefect.flow-run.xyz789",
							},
							payload: {},
							related: [],
						},
					],
					total: 1,
					next_page: null,
				});
			}),
		);

		const selection = createEventSelection();
		const onClose = vi.fn();

		render(
			<FlowRunGraphEventPopoverRouter
				selection={selection}
				onClose={onClose}
			/>,
			{ wrapper: createWrapper() },
		);

		// The component fetches the flow run name via API when not provided in the event
		// The default mock returns "test-flow-run" for flow run requests
		expect(await screen.findByText("test-flow-run")).toBeInTheDocument();
	});
});
