import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { WorkPool } from "@/api/work-pools";

import { WorkPoolDetails } from "./work-pool-details";

// Mock the API modules
vi.mock("@/api/work-pools", () => ({
	buildListWorkPoolWorkersQuery: vi.fn(),
}));

// Mock components
vi.mock("@/components/ui/formatted-date", () => ({
	FormattedDate: ({ date }: { date: string }) => <span>{date}</span>,
}));

vi.mock("@/components/work-pools/work-pool-status-badge", () => ({
	WorkPoolStatusBadge: ({ status }: { status: string }) => (
		<span>Status: {status}</span>
	),
}));

const mockWorkPool: WorkPool = {
	id: "test-id",
	name: "test-work-pool",
	description: "A test work pool",
	type: "docker",
	status: "READY",
	concurrency_limit: 10,
	created: "2024-01-15T10:00:00Z",
	updated: "2024-01-15T12:00:00Z",
	is_paused: false,
	base_job_template: {
		job_configuration: {
			image: "python:3.9",
			command: ["python", "main.py"],
			env: {
				NODE_ENV: "production",
			},
		},
		variables: {
			image: {
				type: "string",
				default: "python:3.9",
				title: "Docker Image",
				description: "The Docker image to use",
			},
		},
	},
};

const createWrapper = () => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: {
				retry: false,
			},
		},
	});
	return ({ children }: { children: React.ReactNode }) => (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);
};

describe("WorkPoolDetails", () => {
	it("renders basic work pool information", () => {
		render(<WorkPoolDetails workPool={mockWorkPool} />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByText("Basic Information")).toBeInTheDocument();
		expect(screen.getByText("Status: READY")).toBeInTheDocument();
		expect(screen.getByText("A test work pool")).toBeInTheDocument();
		expect(screen.getByText("Docker")).toBeInTheDocument();
		expect(screen.getByText("10")).toBeInTheDocument(); // concurrency limit
		expect(screen.getByText("2024-01-15T10:00:00Z")).toBeInTheDocument(); // created
		expect(screen.getByText("2024-01-15T12:00:00Z")).toBeInTheDocument(); // updated
	});

	it("renders job template configuration when present", () => {
		render(<WorkPoolDetails workPool={mockWorkPool} />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByText("Base Job Template")).toBeInTheDocument();
	});

	it("hides job template when not present", () => {
		const workPoolWithoutTemplate = {
			...mockWorkPool,
			base_job_template: undefined,
		};

		render(<WorkPoolDetails workPool={workPoolWithoutTemplate} />, {
			wrapper: createWrapper(),
		});

		expect(screen.queryByText("Base Job Template")).not.toBeInTheDocument();
	});

	it("handles alternate layout properly", () => {
		const { container } = render(
			<WorkPoolDetails workPool={mockWorkPool} alternate={true} />,
			{ wrapper: createWrapper() },
		);

		expect(container.firstChild).toHaveClass("space-y-4");
	});

	it("applies default layout", () => {
		const { container } = render(
			<WorkPoolDetails workPool={mockWorkPool} alternate={false} />,
			{ wrapper: createWrapper() },
		);

		expect(container.firstChild).toHaveClass("space-y-6");
	});

	it("applies custom className", () => {
		const { container } = render(
			<WorkPoolDetails workPool={mockWorkPool} className="custom-class" />,
			{ wrapper: createWrapper() },
		);

		expect(container.firstChild).toHaveClass("custom-class");
	});

	it("handles missing optional fields gracefully", () => {
		const minimalWorkPool = {
			...mockWorkPool,
			description: null,
			concurrency_limit: null,
			created: null,
			updated: null,
		};

		render(<WorkPoolDetails workPool={minimalWorkPool} />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByText("Basic Information")).toBeInTheDocument();
		expect(screen.getByText("Unlimited")).toBeInTheDocument(); // concurrency limit
		// Description should be hidden when not present
		expect(screen.queryByText("Description")).not.toBeInTheDocument();
	});
});
