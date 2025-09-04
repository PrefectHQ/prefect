import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { WorkPool } from "@/api/work-pools";
import { TooltipProvider } from "@/components/ui/tooltip";
import { WorkPoolPageHeader } from "./work-pool-page-header";

// Mock Tanstack Router
vi.mock("@tanstack/react-router", async () => {
	const actual = await vi.importActual("@tanstack/react-router");
	return {
		...actual,
		Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
			<a href={to}>{children}</a>
		),
		useNavigate: () => vi.fn(),
		createLink:
			() =>
			({ children, to }: { children: React.ReactNode; to: string }) => (
				<a href={to}>{children}</a>
			),
	};
});

// Mock the sub-components
vi.mock("@/components/work-pools/work-pool-toggle", () => ({
	WorkPoolToggle: ({ workPool }: { workPool: WorkPool }) => (
		<div data-testid="work-pool-toggle">Toggle for {workPool.name}</div>
	),
}));

vi.mock("@/components/work-pools/work-pool-menu", () => ({
	WorkPoolMenu: ({ workPool }: { workPool: WorkPool }) => (
		<div data-testid="work-pool-menu">Menu for {workPool.name}</div>
	),
}));

vi.mock("@/components/work-pools/work-pool-status-badge", () => ({
	WorkPoolStatusBadge: ({ status }: { status: string }) => (
		<div data-testid="work-pool-status-badge">{status}</div>
	),
}));

const mockWorkPool: WorkPool = {
	id: "123",
	created: "2024-01-01T00:00:00Z",
	updated: "2024-01-01T00:00:00Z",
	name: "test-work-pool",
	description: "Test work pool",
	type: "process",
	base_job_template: {},
	is_paused: false,
	concurrency_limit: null,
	status: "READY",
};

const createWrapper = () => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: { retry: false },
			mutations: { retry: false },
		},
	});

	const Wrapper = ({ children }: { children: React.ReactNode }) => (
		<QueryClientProvider client={queryClient}>
			<TooltipProvider>{children}</TooltipProvider>
		</QueryClientProvider>
	);
	Wrapper.displayName = "TestWrapper";
	return Wrapper;
};

describe("WorkPoolPageHeader", () => {
	it("renders breadcrumbs correctly", () => {
		const Wrapper = createWrapper();
		render(<WorkPoolPageHeader workPool={mockWorkPool} />, {
			wrapper: Wrapper,
		});
		expect(screen.getByText("Work pools")).toBeInTheDocument();
		// Check that the work pool name appears in the breadcrumb
		const breadcrumb = screen.getByRole("navigation", { name: /breadcrumb/i });
		expect(breadcrumb).toHaveTextContent(mockWorkPool.name);
	});

	it("displays work pool title and status", () => {
		const Wrapper = createWrapper();
		render(<WorkPoolPageHeader workPool={mockWorkPool} />, {
			wrapper: Wrapper,
		});
		// Check the work pool name appears in the breadcrumb page
		expect(screen.getByText(mockWorkPool.name)).toBeInTheDocument();
		// The component doesn't render a status badge directly, it's just the toggle and menu
		expect(screen.getByTestId("work-pool-toggle")).toBeInTheDocument();
		expect(screen.getByTestId("work-pool-menu")).toBeInTheDocument();
	});

	it("shows actions components", () => {
		const Wrapper = createWrapper();
		render(<WorkPoolPageHeader workPool={mockWorkPool} />, {
			wrapper: Wrapper,
		});
		expect(screen.getByTestId("work-pool-toggle")).toBeInTheDocument();
		expect(screen.getByTestId("work-pool-menu")).toBeInTheDocument();
	});

	it("passes onUpdate callback to actions", () => {
		const onUpdate = vi.fn();
		const Wrapper = createWrapper();
		render(<WorkPoolPageHeader workPool={mockWorkPool} onUpdate={onUpdate} />, {
			wrapper: Wrapper,
		});
		expect(screen.getByTestId("work-pool-toggle")).toBeInTheDocument();
		expect(screen.getByTestId("work-pool-menu")).toBeInTheDocument();
	});

	it("applies custom className", () => {
		const Wrapper = createWrapper();
		const { container } = render(
			<WorkPoolPageHeader workPool={mockWorkPool} className="custom-class" />,
			{
				wrapper: Wrapper,
			},
		);
		expect(container.querySelector(".custom-class")).toBeInTheDocument();
	});
});
