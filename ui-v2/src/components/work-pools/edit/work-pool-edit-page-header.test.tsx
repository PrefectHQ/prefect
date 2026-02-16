import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { createFakeWorkPool } from "@/mocks/create-fake-work-pool";
import { WorkPoolEditPageHeader } from "./work-pool-edit-page-header";

vi.mock("@tanstack/react-router", async () => {
	const actual = await vi.importActual("@tanstack/react-router");
	return {
		...actual,
		Link: ({
			children,
			to,
			params,
		}: {
			children: React.ReactNode;
			to: string;
			params?: Record<string, string>;
		}) => {
			let href = to;
			if (params) {
				Object.entries(params).forEach(([key, value]) => {
					href = href.replace(`$${key}`, value);
				});
			}
			return <a href={href}>{children}</a>;
		},
		useNavigate: () => vi.fn(),
		createLink:
			() =>
			({
				children,
				to,
				params,
			}: {
				children: React.ReactNode;
				to: string;
				params?: Record<string, string>;
			}) => {
				let href = to;
				if (params) {
					Object.entries(params).forEach(([key, value]) => {
						href = href.replace(`$${key}`, value);
					});
				}
				return <a href={href}>{children}</a>;
			},
	};
});

const createWrapper = () => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: { retry: false },
			mutations: { retry: false },
		},
	});

	const Wrapper = ({ children }: { children: React.ReactNode }) => (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);
	Wrapper.displayName = "TestWrapper";
	return Wrapper;
};

describe("WorkPoolEditPageHeader", () => {
	it("renders breadcrumbs correctly", () => {
		const mockWorkPool = createFakeWorkPool({ name: "test-work-pool" });
		const Wrapper = createWrapper();
		render(<WorkPoolEditPageHeader workPool={mockWorkPool} />, {
			wrapper: Wrapper,
		});

		const breadcrumb = screen.getByRole("navigation", { name: /breadcrumb/i });
		expect(breadcrumb).toBeInTheDocument();
		expect(screen.getByText("Work Pools")).toBeInTheDocument();
		expect(screen.getByText("test-work-pool")).toBeInTheDocument();
		expect(screen.getByText("Edit")).toBeInTheDocument();
	});

	it("renders correct link destinations", () => {
		const mockWorkPool = createFakeWorkPool({ name: "my-pool" });
		const Wrapper = createWrapper();
		render(<WorkPoolEditPageHeader workPool={mockWorkPool} />, {
			wrapper: Wrapper,
		});

		const workPoolsLink = screen.getByRole("link", { name: "Work Pools" });
		expect(workPoolsLink).toHaveAttribute("href", "/work-pools");

		const workPoolLink = screen.getByRole("link", { name: "my-pool" });
		expect(workPoolLink).toHaveAttribute(
			"href",
			"/work-pools/work-pool/my-pool",
		);
	});

	it("displays work pool name accurately", () => {
		const mockWorkPool = createFakeWorkPool({
			name: "production-kubernetes-pool",
		});
		const Wrapper = createWrapper();
		render(<WorkPoolEditPageHeader workPool={mockWorkPool} />, {
			wrapper: Wrapper,
		});

		expect(screen.getByText("production-kubernetes-pool")).toBeInTheDocument();
	});

	it("has accessible breadcrumb navigation role", () => {
		const mockWorkPool = createFakeWorkPool({ name: "test-pool" });
		const Wrapper = createWrapper();
		render(<WorkPoolEditPageHeader workPool={mockWorkPool} />, {
			wrapper: Wrapper,
		});

		const nav = screen.getByRole("navigation", { name: /breadcrumb/i });
		expect(nav).toBeInTheDocument();
	});

	it("renders Edit as current page (not a link)", () => {
		const mockWorkPool = createFakeWorkPool({ name: "test-pool" });
		const Wrapper = createWrapper();
		render(<WorkPoolEditPageHeader workPool={mockWorkPool} />, {
			wrapper: Wrapper,
		});

		const editText = screen.getByText("Edit");
		expect(editText).toBeInTheDocument();
		expect(editText.closest("a")).toBeNull();
		expect(editText).toHaveAttribute("aria-current", "page");
	});

	it("wraps content in header element with correct margin", () => {
		const mockWorkPool = createFakeWorkPool({ name: "test-pool" });
		const Wrapper = createWrapper();
		const { container } = render(
			<WorkPoolEditPageHeader workPool={mockWorkPool} />,
			{
				wrapper: Wrapper,
			},
		);

		const header = container.querySelector("header");
		expect(header).toBeInTheDocument();
		expect(header).toHaveClass("mb-6");
	});
});
