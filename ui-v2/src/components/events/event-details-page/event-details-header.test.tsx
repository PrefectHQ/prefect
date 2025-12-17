import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	Outlet,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import { createContext, type ReactNode, useContext } from "react";
import { describe, expect, it } from "vitest";
import { createFakeEvent } from "@/mocks";
import { EventDetailsHeader } from "./event-details-header";

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

const renderWithProviders = async (ui: ReactNode) => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: {
				retry: false,
			},
		},
	});

	const rootRoute = createRootRoute({
		component: RenderTestChildren,
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
	});

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

describe("EventDetailsHeader", () => {
	describe("breadcrumb rendering", () => {
		it("renders breadcrumb with 'Event Feed' link", async () => {
			const event = createFakeEvent({
				event: "prefect.flow-run.Completed",
			});
			await renderWithProviders(<EventDetailsHeader event={event} />);

			const link = screen.getByRole("link", { name: "Event Feed" });
			expect(link).toBeVisible();
		});

		it("links 'Event Feed' to /events route", async () => {
			const event = createFakeEvent({
				event: "prefect.flow-run.Completed",
			});
			await renderWithProviders(<EventDetailsHeader event={event} />);

			const link = screen.getByRole("link", { name: "Event Feed" });
			expect(link).toHaveAttribute("href", "/events");
		});

		it("formats and displays event label correctly for flow-run event", async () => {
			const event = createFakeEvent({
				event: "prefect.flow-run.Completed",
			});
			await renderWithProviders(<EventDetailsHeader event={event} />);

			expect(screen.getByText("Flow Run Completed")).toBeVisible();
		});

		it("formats and displays event label correctly for task-run event", async () => {
			const event = createFakeEvent({
				event: "prefect.task-run.Running",
			});
			await renderWithProviders(<EventDetailsHeader event={event} />);

			expect(screen.getByText("Task Run Running")).toBeVisible();
		});

		it("formats and displays event label correctly for deployment event", async () => {
			const event = createFakeEvent({
				event: "prefect.deployment.Created",
			});
			await renderWithProviders(<EventDetailsHeader event={event} />);

			expect(screen.getByText("Deployment Created")).toBeVisible();
		});

		it("formats and displays event label correctly for prefect-cloud events", async () => {
			const event = createFakeEvent({
				event: "prefect-cloud.automation.triggered",
			});
			await renderWithProviders(<EventDetailsHeader event={event} />);

			expect(screen.getByText("Automation Triggered")).toBeVisible();
		});

		it("renders breadcrumb separator between items", async () => {
			const event = createFakeEvent({
				event: "prefect.flow-run.Completed",
			});
			const { container } = await renderWithProviders(
				<EventDetailsHeader event={event} />,
			);

			const separator = container.querySelector(
				'[data-slot="breadcrumb-separator"]',
			);
			expect(separator).toBeInTheDocument();
		});
	});
});
