import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import { buildApiUrl, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { Suspense } from "react";
import { beforeEach, describe, expect, it } from "vitest";
import { createFakeEvent } from "@/mocks";
import { EventDetailsPage } from "./event-details-page";

const fakeEvent = createFakeEvent({
	id: "test-event-id",
	event: "prefect.flow-run.Completed",
	occurred: "2024-06-15T14:30:45.000Z",
});

const eventDate = new Date("2024-06-15T14:30:45.000Z");

const EventDetailsPageRouter = () => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: {
				retry: false,
			},
		},
	});

	const rootRoute = createRootRoute({
		component: () => (
			<QueryClientProvider client={queryClient}>
				<Suspense fallback={<div>Loading...</div>}>
					<EventDetailsPage eventId="test-event-id" eventDate={eventDate} />
				</Suspense>
			</QueryClientProvider>
		),
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({
			initialEntries: ["/"],
		}),
		context: { queryClient },
	});

	return <RouterProvider router={router} />;
};

beforeEach(() => {
	server.use(
		http.post(buildApiUrl("/events/filter"), () => {
			return HttpResponse.json({
				events: [fakeEvent],
				total: 1,
				next_page: null,
			});
		}),
	);
});

describe("EventDetailsPage", () => {
	it("renders header component with event data", async () => {
		render(<EventDetailsPageRouter />);

		await waitFor(() => {
			expect(screen.getByText("Event Feed")).toBeInTheDocument();
		});
	});

	it("renders action menu component", async () => {
		render(<EventDetailsPageRouter />);

		await waitFor(() => {
			expect(
				screen.getByRole("button", { name: /event actions/i }),
			).toBeInTheDocument();
		});
	});

	it("renders tabs component with details and raw tabs", async () => {
		render(<EventDetailsPageRouter />);

		await waitFor(() => {
			expect(screen.getByRole("tab", { name: "Details" })).toBeInTheDocument();
			expect(screen.getByRole("tab", { name: "Raw" })).toBeInTheDocument();
		});
	});

	it("fetches event data using the query", async () => {
		render(<EventDetailsPageRouter />);

		await waitFor(() => {
			expect(screen.getByText("Occurred")).toBeInTheDocument();
		});
	});
});
