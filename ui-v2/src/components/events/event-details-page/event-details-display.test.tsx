import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Event } from "@/api/events";
import { EventDetailsDisplay } from "./event-details-display";

const createMockEvent = (overrides: Partial<Event> = {}): Event => ({
	id: "test-event-id",
	occurred: "2024-06-15T14:30:45.000Z",
	event: "prefect.flow-run.Completed",
	resource: {
		"prefect.resource.id": "prefect.flow-run.abc-123",
		"prefect.resource.name": "my-flow-run",
	},
	related: [],
	payload: {},
	received: new Date().toISOString(),
	...overrides,
});

describe("EventDetailsDisplay", () => {
	it("renders event name correctly formatted", () => {
		const event = createMockEvent({
			event: "prefect.flow-run.Completed",
		});
		render(<EventDetailsDisplay event={event} />);

		expect(screen.getByText("Event")).toBeInTheDocument();
		expect(screen.getByText("Flow Run Completed")).toBeInTheDocument();
	});

	it("renders occurred time in correct format (yyyy/MM/dd hh:mm:ss a)", () => {
		const event = createMockEvent({
			occurred: "2024-06-15T14:30:45.000Z",
		});
		render(<EventDetailsDisplay event={event} />);

		expect(screen.getByText("Occurred")).toBeInTheDocument();
		expect(screen.getByText("2024/06/15 02:30:45 PM")).toBeInTheDocument();
	});

	it("renders EventResourceDisplay component", () => {
		const event = createMockEvent({
			resource: {
				"prefect.resource.id": "prefect.flow-run.abc-123",
				"prefect.resource.name": "test-flow-run",
			},
		});
		render(<EventDetailsDisplay event={event} />);

		expect(screen.getByText("Resource")).toBeInTheDocument();
		expect(screen.getByText("test-flow-run")).toBeInTheDocument();
	});

	it("renders tags as badges when present", () => {
		const event = createMockEvent({
			related: [
				{
					"prefect.resource.id": "prefect.tag.production",
					"prefect.resource.role": "tag",
				},
				{
					"prefect.resource.id": "prefect.tag.critical",
					"prefect.resource.role": "tag",
				},
			],
		});
		render(<EventDetailsDisplay event={event} />);

		expect(screen.getByText("Tags")).toBeInTheDocument();
		expect(screen.getByText("production")).toBeInTheDocument();
		expect(screen.getByText("critical")).toBeInTheDocument();
	});

	it("handles events with no related resources or tags (empty state)", () => {
		const event = createMockEvent({
			related: [],
		});
		render(<EventDetailsDisplay event={event} />);

		expect(screen.getByText("Event")).toBeInTheDocument();
		expect(screen.getByText("Occurred")).toBeInTheDocument();
		expect(screen.getByText("Resource")).toBeInTheDocument();
		expect(screen.queryByText("Related Resources")).not.toBeInTheDocument();
		expect(screen.queryByText("Tags")).not.toBeInTheDocument();
	});

	it("renders related resources with icons and type labels", () => {
		const event = createMockEvent({
			related: [
				{
					"prefect.resource.id": "prefect.flow.flow-123",
					"prefect.resource.role": "flow",
					"prefect.resource.name": "my-flow",
				},
				{
					"prefect.resource.id": "prefect.deployment.deploy-456",
					"prefect.resource.role": "deployment",
					"prefect.resource.name": "my-deployment",
				},
			],
		});
		render(<EventDetailsDisplay event={event} />);

		expect(screen.getByText("Related Resources")).toBeInTheDocument();
		expect(screen.getByText("Flow")).toBeInTheDocument();
		expect(screen.getByText("my-flow")).toBeInTheDocument();
		expect(screen.getByText("Deployment")).toBeInTheDocument();
		expect(screen.getByText("my-deployment")).toBeInTheDocument();
	});

	it("separates tags from other related resources", () => {
		const event = createMockEvent({
			related: [
				{
					"prefect.resource.id": "prefect.flow.flow-123",
					"prefect.resource.role": "flow",
					"prefect.resource.name": "my-flow",
				},
				{
					"prefect.resource.id": "prefect.tag.production",
					"prefect.resource.role": "tag",
				},
			],
		});
		render(<EventDetailsDisplay event={event} />);

		expect(screen.getByText("Related Resources")).toBeInTheDocument();
		expect(screen.getByText("Tags")).toBeInTheDocument();
		expect(screen.getByText("my-flow")).toBeInTheDocument();
		expect(screen.getByText("production")).toBeInTheDocument();
	});

	it("uses resource name from prefect.name fallback", () => {
		const event = createMockEvent({
			related: [
				{
					"prefect.resource.id": "prefect.flow.flow-123",
					"prefect.resource.role": "flow",
					"prefect.name": "fallback-name",
				},
			],
		});
		render(<EventDetailsDisplay event={event} />);

		expect(screen.getByText("fallback-name")).toBeInTheDocument();
	});

	it("uses resource ID when no name is available", () => {
		const event = createMockEvent({
			related: [
				{
					"prefect.resource.id": "prefect.flow.flow-123",
					"prefect.resource.role": "flow",
				},
			],
		});
		render(<EventDetailsDisplay event={event} />);

		expect(screen.getByText("prefect.flow.flow-123")).toBeInTheDocument();
	});

	it("handles undefined related array", () => {
		const event: Event = {
			id: "test-event-id",
			occurred: "2024-06-15T14:30:45.000Z",
			event: "prefect.flow-run.Completed",
			resource: {
				"prefect.resource.id": "prefect.flow-run.abc-123",
				"prefect.resource.name": "my-flow-run",
			},
			payload: {},
			received: new Date().toISOString(),
		};
		render(<EventDetailsDisplay event={event} />);

		expect(screen.getByText("Event")).toBeInTheDocument();
		expect(screen.queryByText("Related Resources")).not.toBeInTheDocument();
		expect(screen.queryByText("Tags")).not.toBeInTheDocument();
	});

	it("extracts tag name from resource ID when no name is provided", () => {
		const event = createMockEvent({
			related: [
				{
					"prefect.resource.id": "prefect.tag.my-custom-tag",
					"prefect.resource.role": "tag",
				},
			],
		});
		render(<EventDetailsDisplay event={event} />);

		expect(screen.getByText("my-custom-tag")).toBeInTheDocument();
	});
});
