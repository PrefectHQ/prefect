import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RouteComponent } from "./dashboard";

const createWrapper = () => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: {
				retry: false,
			},
		},
	});

	return function TestWrapper({ children }: { children: React.ReactNode }) {
		return (
			<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
		);
	};
};

describe("Dashboard Route", () => {
	it("renders the dashboard page with proper heading", () => {
		const Wrapper = createWrapper();

		render(<RouteComponent />, { wrapper: Wrapper });

		expect(screen.getByText("Dashboard")).toBeInTheDocument();
	});

	it("renders the dashboard page with responsive grid layout", () => {
		const Wrapper = createWrapper();

		const { container } = render(<RouteComponent />, {
			wrapper: Wrapper,
		});

		// Check for the main grid container
		const gridContainer = container.querySelector(
			".grid.grid-cols-1.gap-4.items-start.xl\\:grid-cols-2",
		);
		expect(gridContainer).toBeInTheDocument();
	});

	it("displays placeholder sections for future components", () => {
		const Wrapper = createWrapper();

		render(<RouteComponent />, { wrapper: Wrapper });

		// Check for placeholder content
		expect(screen.getByText("Flow Runs")).toBeInTheDocument();
		expect(screen.getByText("Cumulative Task Runs")).toBeInTheDocument();
		expect(screen.getByText("Work Pools")).toBeInTheDocument();

		// Check for placeholder text
		expect(
			screen.getByText("Flow runs chart and table will appear here"),
		).toBeInTheDocument();
		expect(
			screen.getByText("Cumulative task runs chart will appear here"),
		).toBeInTheDocument();
		expect(
			screen.getByText("Work pools status will appear here"),
		).toBeInTheDocument();
	});

	it("renders breadcrumb navigation", () => {
		const Wrapper = createWrapper();

		render(<RouteComponent />, { wrapper: Wrapper });

		// Check for breadcrumb navigation
		const breadcrumbNav = screen.getByRole("navigation", {
			name: "Breadcrumb",
		});
		expect(breadcrumbNav).toBeInTheDocument();
	});

	it("includes filter control placeholders for future implementation", () => {
		const Wrapper = createWrapper();

		const { container } = render(<RouteComponent />, {
			wrapper: Wrapper,
		});

		// Check for filter control placeholders (skeleton components)
		const skeletonElements = container.querySelectorAll(".animate-pulse");
		expect(skeletonElements.length).toBeGreaterThan(0);
	});
});
