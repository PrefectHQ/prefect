import { render, screen, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { Suspense } from "react";
import { describe, expect, it } from "vitest";
import type { Event } from "@/api/events";
import { createFakeFlowRun } from "@/mocks";
import {
	EventResourceDisplay,
	ResourceDisplaySkeleton,
	ResourceDisplayWithIcon,
} from "./event-resource-display";

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
	it("renders with resource name and icon for flow-run", () => {
		const event = createMockEvent("prefect.flow-run.abc-123", "My Flow Run");
		render(<EventResourceDisplay event={event} />);

		expect(screen.getByText("Resource")).toBeInTheDocument();
		expect(screen.getByText("My Flow Run")).toBeInTheDocument();
	});

	it("renders with resource name and icon for deployment", () => {
		const event = createMockEvent(
			"prefect.deployment.abc-123",
			"My Deployment",
		);
		render(<EventResourceDisplay event={event} />);

		expect(screen.getByText("Resource")).toBeInTheDocument();
		expect(screen.getByText("My Deployment")).toBeInTheDocument();
	});

	it("renders with resource name and icon for flow", () => {
		const event = createMockEvent("prefect.flow.abc-123", "My Flow");
		render(<EventResourceDisplay event={event} />);

		expect(screen.getByText("Resource")).toBeInTheDocument();
		expect(screen.getByText("My Flow")).toBeInTheDocument();
	});

	it("renders with resource name and icon for work-pool", () => {
		const event = createMockEvent("prefect.work-pool.abc-123", "My Work Pool");
		render(<EventResourceDisplay event={event} />);

		expect(screen.getByText("Resource")).toBeInTheDocument();
		expect(screen.getByText("My Work Pool")).toBeInTheDocument();
	});

	it("renders with resource name and icon for work-queue", () => {
		const event = createMockEvent(
			"prefect.work-queue.abc-123",
			"My Work Queue",
		);
		render(<EventResourceDisplay event={event} />);

		expect(screen.getByText("Resource")).toBeInTheDocument();
		expect(screen.getByText("My Work Queue")).toBeInTheDocument();
	});

	it("renders with resource name and icon for automation", () => {
		const event = createMockEvent(
			"prefect.automation.abc-123",
			"My Automation",
		);
		render(<EventResourceDisplay event={event} />);

		expect(screen.getByText("Resource")).toBeInTheDocument();
		expect(screen.getByText("My Automation")).toBeInTheDocument();
	});

	it("renders with resource name and icon for block-document", () => {
		const event = createMockEvent("prefect.block-document.abc-123", "My Block");
		render(<EventResourceDisplay event={event} />);

		expect(screen.getByText("Resource")).toBeInTheDocument();
		expect(screen.getByText("My Block")).toBeInTheDocument();
	});

	it("renders with resource name and icon for concurrency-limit", () => {
		const event = createMockEvent(
			"prefect.concurrency-limit.abc-123",
			"My Limit",
		);
		render(<EventResourceDisplay event={event} />);

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
		render(
			<Suspense fallback={<div>Loading...</div>}>
				<EventResourceDisplay event={event} />
			</Suspense>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Resource")).toBeInTheDocument();
		// The component now fetches the resource name via API
		await waitFor(() => {
			expect(screen.getByText("fetched-flow-run-name")).toBeInTheDocument();
		});
	});

	it("renders raw resource ID for unknown resource types", () => {
		const event = createMockEvent("some.unknown.resource");
		render(<EventResourceDisplay event={event} />);

		expect(screen.getByText("Resource")).toBeInTheDocument();
		expect(screen.getByText("resource")).toBeInTheDocument();
	});

	it("renders Unknown when no resource information is available", () => {
		const event: Event = {
			id: "test-event-id",
			occurred: new Date().toISOString(),
			event: "test.event",
			resource: {},
			related: [],
			payload: {},
			received: new Date().toISOString(),
		};
		render(<EventResourceDisplay event={event} />);

		expect(screen.getByText("Resource")).toBeInTheDocument();
		expect(screen.getByText("Unknown")).toBeInTheDocument();
	});

	it("applies custom className", () => {
		const event = createMockEvent("prefect.flow-run.abc-123", "My Flow Run");
		const { container } = render(
			<EventResourceDisplay event={event} className="custom-class" />,
		);

		expect(container.firstChild).toHaveClass("custom-class");
	});

	it("uses prefect.name as fallback for resource name", () => {
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
		render(<EventResourceDisplay event={event} />);

		expect(screen.getByText("Fallback Name")).toBeInTheDocument();
	});

	it("uses prefect-cloud.name as fallback for resource name", () => {
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
		render(<EventResourceDisplay event={event} />);

		expect(screen.getByText("Cloud Name")).toBeInTheDocument();
	});
});

describe("ResourceDisplayWithIcon", () => {
	it("renders with flow-run icon", () => {
		render(
			<ResourceDisplayWithIcon resourceType="flow-run" displayText="Test" />,
		);
		expect(screen.getByText("Test")).toBeInTheDocument();
	});

	it("renders with deployment icon", () => {
		render(
			<ResourceDisplayWithIcon resourceType="deployment" displayText="Test" />,
		);
		expect(screen.getByText("Test")).toBeInTheDocument();
	});

	it("renders with unknown icon", () => {
		render(
			<ResourceDisplayWithIcon resourceType="unknown" displayText="Test" />,
		);
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
