import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { createFakeEvent } from "@/mocks";
import { EventDetailsTabs } from "./event-details-tabs";

describe("EventDetailsTabs", () => {
	it("renders both tabs (Details and Raw)", () => {
		const event = createFakeEvent();
		render(<EventDetailsTabs event={event} />);

		expect(screen.getByRole("tab", { name: "Details" })).toBeInTheDocument();
		expect(screen.getByRole("tab", { name: "Raw" })).toBeInTheDocument();
	});

	it("defaults to Details tab", () => {
		const event = createFakeEvent();
		render(<EventDetailsTabs event={event} />);

		const detailsTab = screen.getByRole("tab", { name: "Details" });
		expect(detailsTab).toHaveAttribute("data-state", "active");
	});

	it("switches tabs when clicking Raw tab", async () => {
		const user = userEvent.setup();
		const event = createFakeEvent();
		render(<EventDetailsTabs event={event} />);

		const rawTab = screen.getByRole("tab", { name: "Raw" });
		await user.click(rawTab);

		expect(rawTab).toHaveAttribute("data-state", "active");
		expect(screen.getByRole("tab", { name: "Details" })).toHaveAttribute(
			"data-state",
			"inactive",
		);
	});

	it("renders EventDetailsDisplay component in Details tab", () => {
		const event = createFakeEvent({
			event: "prefect.flow-run.Completed",
		});
		render(<EventDetailsTabs event={event} />);

		expect(screen.getByText("Event")).toBeInTheDocument();
		expect(screen.getByText("Flow Run Completed")).toBeInTheDocument();
	});

	it("renders JSON view with event data in Raw tab", async () => {
		const user = userEvent.setup();
		const event = createFakeEvent({
			id: "test-event-id-123",
			event: "prefect.flow-run.Completed",
		});
		render(<EventDetailsTabs event={event} />);

		const rawTab = screen.getByRole("tab", { name: "Raw" });
		await user.click(rawTab);

		expect(screen.getByText(/test-event-id-123/)).toBeInTheDocument();
	});

	it("respects defaultTab prop when set to raw", () => {
		const event = createFakeEvent();
		render(<EventDetailsTabs event={event} defaultTab="raw" />);

		const rawTab = screen.getByRole("tab", { name: "Raw" });
		expect(rawTab).toHaveAttribute("data-state", "active");
	});

	it("calls onTabChange callback when tab changes", async () => {
		const user = userEvent.setup();
		const event = createFakeEvent();
		const onTabChange = vi.fn();
		render(<EventDetailsTabs event={event} onTabChange={onTabChange} />);

		const rawTab = screen.getByRole("tab", { name: "Raw" });
		await user.click(rawTab);

		expect(onTabChange).toHaveBeenCalledWith("raw");
	});

	it("calls onTabChange callback when switching back to details", async () => {
		const user = userEvent.setup();
		const event = createFakeEvent();
		const onTabChange = vi.fn();
		render(
			<EventDetailsTabs
				event={event}
				defaultTab="raw"
				onTabChange={onTabChange}
			/>,
		);

		const detailsTab = screen.getByRole("tab", { name: "Details" });
		await user.click(detailsTab);

		expect(onTabChange).toHaveBeenCalledWith("details");
	});
});
