import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	Outlet,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createContext, type ReactNode, useContext } from "react";
import { describe, expect, it } from "vitest";
import type { components } from "@/api/prefect";
import { EventsTimeline } from "./events-timeline";
import { formatEventLabel, getEventPrefixes } from "./utilities";

type Event = components["schemas"]["ReceivedEvent"];

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

	const result = render(
		<TestChildrenContext.Provider value={ui}>
			<RouterProvider router={router} />
		</TestChildrenContext.Provider>,
	);

	await waitFor(() => {
		expect(router.state.status).toBe("idle");
	});

	return result;
};

const createMockEvent = (overrides: Partial<Event> = {}): Event => ({
	id: crypto.randomUUID(),
	occurred: new Date().toISOString(),
	event: "prefect.flow-run.Completed",
	resource: {
		"prefect.resource.id": `prefect.flow-run.${crypto.randomUUID()}`,
		"prefect.resource.name": "my-flow-run",
	},
	related: [],
	payload: {},
	...overrides,
});

describe("getEventPrefixes", () => {
	it("returns correct prefixes for a simple event name", () => {
		const result = getEventPrefixes("prefect.flow-run.Completed");
		expect(result).toEqual([
			"prefect.*",
			"prefect.flow-run.*",
			"prefect.flow-run.Completed",
		]);
	});

	it("returns correct prefixes for a deeply nested event name", () => {
		const result = getEventPrefixes("prefect.flow-run.state.Completed");
		expect(result).toEqual([
			"prefect.*",
			"prefect.flow-run.*",
			"prefect.flow-run.state.*",
			"prefect.flow-run.state.Completed",
		]);
	});

	it("returns correct prefixes for a two-part event name", () => {
		const result = getEventPrefixes("prefect.event");
		expect(result).toEqual(["prefect.*", "prefect.event"]);
	});

	it("returns only the event name for a single-part event", () => {
		const result = getEventPrefixes("event");
		expect(result).toEqual(["event"]);
	});
});

describe("formatEventLabel", () => {
	it("formats prefect event names correctly", () => {
		expect(formatEventLabel("prefect.flow-run.Completed")).toBe(
			"Flow Run Completed",
		);
	});

	it("formats prefect-cloud event names correctly", () => {
		expect(formatEventLabel("prefect-cloud.workspace.Created")).toBe(
			"Workspace Created",
		);
	});

	it("handles underscores in event names", () => {
		expect(formatEventLabel("prefect.task_run.Started")).toBe(
			"Task Run Started",
		);
	});

	it("handles mixed separators", () => {
		expect(formatEventLabel("prefect.flow-run_state.Completed")).toBe(
			"Flow Run State Completed",
		);
	});

	it("handles event names without prefect prefix", () => {
		expect(formatEventLabel("custom.event.name")).toBe("Custom Event Name");
	});
});

describe("EventsTimeline", () => {
	it("returns null when events array is empty", async () => {
		const { container } = await renderWithRouter(
			<EventsTimeline events={[]} />,
		);
		expect(container.querySelector("ol")).toBeNull();
	});

	it("renders events when provided", async () => {
		const events = [
			createMockEvent({
				id: "event-1",
				event: "prefect.flow-run.Completed",
				resource: {
					"prefect.resource.id": "prefect.flow-run.123",
					"prefect.resource.name": "test-flow-run",
				},
			}),
		];

		await renderWithRouter(<EventsTimeline events={events} />);

		expect(screen.getByText("Flow Run Completed")).toBeInTheDocument();
		expect(screen.getByText("prefect.flow-run.Completed")).toBeInTheDocument();
	});

	it("renders multiple events", async () => {
		const events = [
			createMockEvent({
				id: "event-1",
				event: "prefect.flow-run.Completed",
			}),
			createMockEvent({
				id: "event-2",
				event: "prefect.task-run.Failed",
			}),
		];

		await renderWithRouter(<EventsTimeline events={events} />);

		expect(screen.getByText("Flow Run Completed")).toBeInTheDocument();
		expect(screen.getByText("Task Run Failed")).toBeInTheDocument();
	});

	it("displays resource information", async () => {
		const events = [
			createMockEvent({
				id: "event-1",
				resource: {
					"prefect.resource.id": "prefect.flow-run.abc123",
					"prefect.resource.name": "my-test-flow",
				},
			}),
		];

		await renderWithRouter(<EventsTimeline events={events} />);

		expect(screen.getByText("my-test-flow")).toBeInTheDocument();
	});

	it("displays related resources with tags as badges", async () => {
		const events = [
			createMockEvent({
				id: "event-1",
				related: [
					{
						"prefect.resource.id": "prefect.tag.production",
						"prefect.resource.role": "tag",
					},
				],
			}),
		];

		await renderWithRouter(<EventsTimeline events={events} />);

		expect(screen.getByText("production")).toBeInTheDocument();
	});

	it("expands to show raw JSON when expand button is clicked", async () => {
		const user = userEvent.setup();
		const events = [
			createMockEvent({
				id: "event-1",
				event: "prefect.flow-run.Completed",
			}),
		];

		await renderWithRouter(<EventsTimeline events={events} />);

		const expandButton = screen.getByRole("button", {
			name: /expand event details/i,
		});
		await user.click(expandButton);

		expect(
			screen.getByRole("button", { name: /collapse event details/i }),
		).toBeInTheDocument();
	});

	it("applies custom className", async () => {
		const events = [createMockEvent({ id: "event-1" })];
		const { container } = await renderWithRouter(
			<EventsTimeline events={events} className="custom-class" />,
		);

		expect(container.querySelector("ol")).toHaveClass("custom-class");
	});
});
