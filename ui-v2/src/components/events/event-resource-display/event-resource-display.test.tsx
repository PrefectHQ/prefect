import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	Outlet,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import { buildApiUrl, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { createContext, type ReactNode, Suspense, useContext } from "react";
import { describe, expect, it } from "vitest";
import type { Event } from "@/api/events";
import { createFakeFlowRun } from "@/mocks";
import {
	EventResourceDisplay,
	ResourceDisplaySkeleton,
	ResourceDisplayWithIcon,
} from "./event-resource-display";

const TestChildrenContext = createContext<ReactNode>(null);

function RenderTestChildren() {
	const children = useContext(TestChildrenContext);
	return (
		<>
			{children}
			<Outlet />
		</>
	);
}

const renderWithRouter = async (ui: ReactNode) => {
	const rootRoute = createRootRoute({
		component: RenderTestChildren,
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
	});

	const queryClient = new QueryClient();

	const result = render(
		<QueryClientProvider client={queryClient}>
			<TestChildrenContext.Provider value={ui}>
				<RouterProvider router={router} />
			</TestChildrenContext.Provider>
		</QueryClientProvider>,
	);

	await waitFor(() => {
		expect(router.state.status).toBe("idle");
	});

	return result;
};

const createMockEvent = (resourceId: string, resourceName?: string): Event => ({
	id: "test-event-id",
	occurred: new Date().toISOString(),
	event: "test.event",
	resource: {
		"prefect.resource.id": resourceId,
		...(resourceName ? { "prefect.resource.name": resourceName } : {}),
	},
	related: [],
	payload: {},
	received: new Date().toISOString(),
});

describe("EventResourceDisplay", () => {
	it("renders with resource name and icon for flow-run", async () => {
		const event = createMockEvent("prefect.flow-run.abc-123", "My Flow Run");
		await renderWithRouter(<EventResourceDisplay event={event} />);

		expect(screen.getByText("Resource")).toBeInTheDocument();
		expect(screen.getByText("My Flow Run")).toBeInTheDocument();
	});

	it("renders with resource name and icon for deployment", async () => {
		const event = createMockEvent(
			"prefect.deployment.abc-123",
			"My Deployment",
		);
		await renderWithRouter(<EventResourceDisplay event={event} />);

		expect(screen.getByText("Resource")).toBeInTheDocument();
		expect(screen.getByText("My Deployment")).toBeInTheDocument();
	});

	it("renders with resource name and icon for flow", async () => {
		const event = createMockEvent("prefect.flow.abc-123", "My Flow");
		await renderWithRouter(<EventResourceDisplay event={event} />);

		expect(screen.getByText("Resource")).toBeInTheDocument();
		expect(screen.getByText("My Flow")).toBeInTheDocument();
	});

	it("renders with resource name and icon for work-pool", async () => {
		const event = createMockEvent("prefect.work-pool.abc-123", "My Work Pool");
		await renderWithRouter(<EventResourceDisplay event={event} />);

		expect(screen.getByText("Resource")).toBeInTheDocument();
		expect(screen.getByText("My Work Pool")).toBeInTheDocument();
	});

	it("renders with resource name and icon for work-queue", async () => {
		const event = createMockEvent(
			"prefect.work-queue.abc-123",
			"My Work Queue",
		);
		await renderWithRouter(<EventResourceDisplay event={event} />);

		expect(screen.getByText("Resource")).toBeInTheDocument();
		expect(screen.getByText("My Work Queue")).toBeInTheDocument();
	});

	it("renders with resource name and icon for automation", async () => {
		const event = createMockEvent(
			"prefect.automation.abc-123",
			"My Automation",
		);
		await renderWithRouter(<EventResourceDisplay event={event} />);

		expect(screen.getByText("Resource")).toBeInTheDocument();
		expect(screen.getByText("My Automation")).toBeInTheDocument();
	});

	it("renders with resource name and icon for block-document", async () => {
		const event = createMockEvent("prefect.block-document.abc-123", "My Block");
		await renderWithRouter(<EventResourceDisplay event={event} />);

		expect(screen.getByText("Resource")).toBeInTheDocument();
		expect(screen.getByText("My Block")).toBeInTheDocument();
	});

	it("renders with resource name and icon for concurrency-limit", async () => {
		const event = createMockEvent(
			"prefect.concurrency-limit.abc-123",
			"My Limit",
		);
		await renderWithRouter(<EventResourceDisplay event={event} />);

		expect(screen.getByText("Resource")).toBeInTheDocument();
		expect(screen.getByText("My Limit")).toBeInTheDocument();
	});

	it("renders extracted ID when no resource name is provided", async () => {
		// When no resource name is provided, the component fetches the resource name via API
		const mockFlowRun = createFakeFlowRun({
			id: "abc-123",
			name: "fetched-flow-run-name",
		});
		server.use(
			http.get(buildApiUrl("/flow_runs/:id"), () => {
				return HttpResponse.json(mockFlowRun);
			}),
		);

		const event = createMockEvent("prefect.flow-run.abc-123");
		await renderWithRouter(
			<Suspense fallback={<div>Loading...</div>}>
				<EventResourceDisplay event={event} />
			</Suspense>,
		);

		expect(screen.getByText("Resource")).toBeInTheDocument();
		// The component now fetches the resource name via API
		await waitFor(() => {
			expect(screen.getByText("fetched-flow-run-name")).toBeInTheDocument();
		});
	});

	it("renders raw resource ID for unknown resource types", async () => {
		const event = createMockEvent("some.unknown.resource");
		await renderWithRouter(<EventResourceDisplay event={event} />);

		// "Resource" appears twice: once as section header, once as type label for unknown types
		const resourceTexts = screen.getAllByText("Resource");
		expect(resourceTexts).toHaveLength(2);
		expect(screen.getByText("resource")).toBeInTheDocument();
	});

	it("renders Unknown when no resource information is available", async () => {
		const event: Event = {
			id: "test-event-id",
			occurred: new Date().toISOString(),
			event: "test.event",
			resource: {},
			related: [],
			payload: {},
			received: new Date().toISOString(),
		};
		await renderWithRouter(<EventResourceDisplay event={event} />);

		expect(screen.getByText("Resource")).toBeInTheDocument();
		expect(screen.getByText("Unknown")).toBeInTheDocument();
	});

	it("applies custom className", async () => {
		const event = createMockEvent("prefect.flow-run.abc-123", "My Flow Run");
		const { container } = await renderWithRouter(
			<EventResourceDisplay event={event} className="custom-class" />,
		);

		expect(container.firstChild).toHaveClass("custom-class");
	});

	it("uses prefect.name as fallback for resource name", async () => {
		const event: Event = {
			id: "test-event-id",
			occurred: new Date().toISOString(),
			event: "test.event",
			resource: {
				"prefect.resource.id": "prefect.flow-run.abc-123",
				"prefect.name": "Fallback Name",
			},
			related: [],
			payload: {},
			received: new Date().toISOString(),
		};
		await renderWithRouter(<EventResourceDisplay event={event} />);

		expect(screen.getByText("Fallback Name")).toBeInTheDocument();
	});

	it("uses prefect-cloud.name as fallback for resource name", async () => {
		const event: Event = {
			id: "test-event-id",
			occurred: new Date().toISOString(),
			event: "test.event",
			resource: {
				"prefect.resource.id": "prefect.flow-run.abc-123",
				"prefect-cloud.name": "Cloud Name",
			},
			related: [],
			payload: {},
			received: new Date().toISOString(),
		};
		await renderWithRouter(<EventResourceDisplay event={event} />);

		expect(screen.getByText("Cloud Name")).toBeInTheDocument();
	});
});

describe("ResourceDisplayWithIcon", () => {
	it("renders with flow-run icon and type label", () => {
		render(
			<ResourceDisplayWithIcon resourceType="flow-run" displayText="Test" />,
		);
		expect(screen.getByText("Flow run")).toBeInTheDocument();
		expect(screen.getByText("Test")).toBeInTheDocument();
	});

	it("renders with deployment icon and type label", () => {
		render(
			<ResourceDisplayWithIcon resourceType="deployment" displayText="Test" />,
		);
		expect(screen.getByText("Deployment")).toBeInTheDocument();
		expect(screen.getByText("Test")).toBeInTheDocument();
	});

	it("renders with unknown icon and type label", () => {
		render(
			<ResourceDisplayWithIcon resourceType="unknown" displayText="Test" />,
		);
		expect(screen.getByText("Resource")).toBeInTheDocument();
		expect(screen.getByText("Test")).toBeInTheDocument();
	});

	it("applies custom className", () => {
		const { container } = render(
			<ResourceDisplayWithIcon
				resourceType="flow-run"
				displayText="Test"
				className="custom-class"
			/>,
		);
		expect(container.firstChild).toHaveClass("custom-class");
	});
});

describe("ResourceDisplaySkeleton", () => {
	it("renders skeleton elements", () => {
		render(<ResourceDisplaySkeleton />);
		const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
		expect(skeletons.length).toBe(2);
	});
});
