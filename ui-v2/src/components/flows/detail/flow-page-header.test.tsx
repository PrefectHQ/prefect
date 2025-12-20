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
import { describe, expect, it, vi } from "vitest";
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
});
