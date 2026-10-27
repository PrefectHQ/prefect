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
import { createContext, type ReactNode, useContext } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createFakeFlow } from "@/mocks";
import { FlowPageHeader } from "./flow-page-header";

const mockOnDelete = vi.fn();

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

describe("FlowPageHeader", () => {
	beforeEach(() => {
		server.use(
			http.post(buildApiUrl("/ui/flows/count-deployments"), () =>
				HttpResponse.json({}),
			),
		);
	});
	describe("breadcrumb rendering", () => {
		it("renders breadcrumb with 'Flows' link", async () => {
			const flow = createFakeFlow({
				name: "my-test-flow",
			});
			await renderWithProviders(
				<FlowPageHeader flow={flow} onDelete={mockOnDelete} />,
			);

			const link = screen.getByRole("link", { name: "Flows" });
			expect(link).toBeVisible();
		});

		it("links 'Flows' to /flows route", async () => {
			const flow = createFakeFlow({
				name: "my-test-flow",
			});
			await renderWithProviders(
				<FlowPageHeader flow={flow} onDelete={mockOnDelete} />,
			);

			const link = screen.getByRole("link", { name: "Flows" });
			expect(link).toHaveAttribute("href", "/flows");
		});

		it("displays flow name correctly", async () => {
			const flow = createFakeFlow({
				name: "my-etl-flow",
			});
			await renderWithProviders(
				<FlowPageHeader flow={flow} onDelete={mockOnDelete} />,
			);

			expect(screen.getByText("my-etl-flow")).toBeVisible();
		});

		it("displays long flow name correctly", async () => {
			const flow = createFakeFlow({
				name: "my-very-long-flow-name-that-might-cause-wrapping",
			});
			await renderWithProviders(
				<FlowPageHeader flow={flow} onDelete={mockOnDelete} />,
			);

			expect(
				screen.getByText("my-very-long-flow-name-that-might-cause-wrapping"),
			).toBeVisible();
		});

		it("renders breadcrumb separator between items", async () => {
			const flow = createFakeFlow({
				name: "my-test-flow",
			});
			const { container } = await renderWithProviders(
				<FlowPageHeader flow={flow} onDelete={mockOnDelete} />,
			);

			const separator = container.querySelector(
				'[data-slot="breadcrumb-separator"]',
			);
			expect(separator).toBeInTheDocument();
		});
	});

	describe("Run action", () => {
		it("shows a disabled Run button when the flow has no deployments", async () => {
			const flow = createFakeFlow();
			server.use(
				http.post(buildApiUrl("/ui/flows/count-deployments"), () =>
					HttpResponse.json({ [flow.id]: 0 }),
				),
			);
			await renderWithProviders(
				<FlowPageHeader flow={flow} onDelete={mockOnDelete} />,
			);

			const button = screen.getByRole("button", { name: /run/i });
			await waitFor(() =>
				expect(button).toHaveAccessibleDescription(
					"Create a deployment to run this flow from the UI.",
				),
			);
			expect(button).toBeDisabled();
		});

		it("shows an enabled Run button when the flow has a deployment", async () => {
			const flow = createFakeFlow();
			server.use(
				http.post(buildApiUrl("/ui/flows/count-deployments"), () =>
					HttpResponse.json({ [flow.id]: 1 }),
				),
			);
			await renderWithProviders(
				<FlowPageHeader flow={flow} onDelete={mockOnDelete} />,
			);

			await waitFor(() =>
				expect(screen.getByRole("button", { name: /run/i })).toBeEnabled(),
			);
		});
	});
});
