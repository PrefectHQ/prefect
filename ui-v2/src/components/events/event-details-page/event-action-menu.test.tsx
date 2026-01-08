import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { createFakeEvent } from "@/mocks";
import { EventActionMenu } from "./event-action-menu";

describe("EventActionMenu", () => {
	const EventActionMenuRouter = ({
		event,
	}: {
		event: ReturnType<typeof createFakeEvent>;
	}) => {
		const rootRoute = createRootRoute({
			component: () => <EventActionMenu event={event} />,
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

	it("opens dropdown menu when trigger is clicked", async () => {
		const user = userEvent.setup();
		const event = createFakeEvent();

		await waitFor(() =>
			render(
				<>
					<Toaster />
					<EventActionMenuRouter event={event} />
				</>,
			),
		);

		await user.click(
			screen.getByRole("button", { name: /event actions/i, hidden: true }),
		);

		expect(screen.getByRole("menuitem", { name: /copy id/i })).toBeVisible();
	});

	it("shows Automate option in dropdown menu", async () => {
		const user = userEvent.setup();
		const event = createFakeEvent();

		await waitFor(() =>
			render(
				<>
					<Toaster />
					<EventActionMenuRouter event={event} />
				</>,
			),
		);

		await user.click(
			screen.getByRole("button", { name: /event actions/i, hidden: true }),
		);

		expect(screen.getByRole("menuitem", { name: /automate/i })).toBeVisible();
	});

	it("copies the event id and shows toast notification", async () => {
		const user = userEvent.setup();
		const event = createFakeEvent({ id: "test-event-id-123" });

		await waitFor(() =>
			render(
				<>
					<Toaster />
					<EventActionMenuRouter event={event} />
				</>,
			),
		);

		await user.click(
			screen.getByRole("button", { name: /event actions/i, hidden: true }),
		);
		await user.click(screen.getByRole("menuitem", { name: /copy id/i }));

		await waitFor(() => {
			expect(screen.getByText("ID copied")).toBeVisible();
		});
	});

	it("Automate link includes eventId and eventDate search parameters", async () => {
		const user = userEvent.setup();
		const event = createFakeEvent({
			id: "test-event-id-456",
			occurred: "2024-06-15T10:30:00Z",
		});

		await waitFor(() =>
			render(
				<>
					<Toaster />
					<EventActionMenuRouter event={event} />
				</>,
			),
		);

		await user.click(
			screen.getByRole("button", { name: /event actions/i, hidden: true }),
		);

		const automateLink = screen.getByRole("link", { name: /automate/i });
		expect(automateLink).toBeVisible();
		expect(automateLink).toHaveAttribute(
			"href",
			expect.stringContaining("eventId=test-event-id-456"),
		);
		expect(automateLink).toHaveAttribute(
			"href",
			expect.stringContaining("eventDate=2024-06-15"),
		);
	});
});
