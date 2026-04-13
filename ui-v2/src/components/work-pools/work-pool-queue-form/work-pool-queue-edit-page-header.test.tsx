import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkPoolQueueEditPageHeader } from "./work-pool-queue-edit-page-header";

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

describe("WorkPoolQueueEditPageHeader", () => {
	it("renders breadcrumbs correctly", () => {
		const Wrapper = createWrapper();
		render(
			<WorkPoolQueueEditPageHeader
				workPoolName="test-pool"
				workQueueName="test-queue"
			/>,
			{ wrapper: Wrapper },
		);

		const breadcrumb = screen.getByRole("navigation", { name: /breadcrumb/i });
		expect(breadcrumb).toBeInTheDocument();
		expect(screen.getByText("Work Pools")).toBeInTheDocument();
		expect(screen.getByText("test-pool")).toBeInTheDocument();
		expect(screen.getByText("test-queue")).toBeInTheDocument();
		expect(screen.getByText("Edit")).toBeInTheDocument();
	});

	it("renders correct link destinations", () => {
		const Wrapper = createWrapper();
		render(
			<WorkPoolQueueEditPageHeader
				workPoolName="my-pool"
				workQueueName="my-queue"
			/>,
			{ wrapper: Wrapper },
		);

		const workPoolsLink = screen.getByRole("link", { name: "Work Pools" });
		expect(workPoolsLink).toHaveAttribute("href", "/work-pools");

		const workPoolLink = screen.getByRole("link", { name: "my-pool" });
		expect(workPoolLink).toHaveAttribute(
			"href",
			"/work-pools/work-pool/my-pool",
		);

		const queueLink = screen.getByRole("link", { name: "my-queue" });
		expect(queueLink).toHaveAttribute(
			"href",
			"/work-pools/work-pool/my-pool/queue/my-queue",
		);
	});

	it("renders Edit as current page (not a link)", () => {
		const Wrapper = createWrapper();
		render(
			<WorkPoolQueueEditPageHeader
				workPoolName="test-pool"
				workQueueName="test-queue"
			/>,
			{ wrapper: Wrapper },
		);

		const editText = screen.getByText("Edit");
		expect(editText).toBeInTheDocument();
		expect(editText.closest("a")).toBeNull();
		expect(editText).toHaveAttribute("aria-current", "page");
	});

	it("wraps content in a header element", () => {
		const Wrapper = createWrapper();
		const { container } = render(
			<WorkPoolQueueEditPageHeader
				workPoolName="test-pool"
				workQueueName="test-queue"
			/>,
			{ wrapper: Wrapper },
		);

		const header = container.querySelector("header");
		expect(header).toBeInTheDocument();
	});
});
