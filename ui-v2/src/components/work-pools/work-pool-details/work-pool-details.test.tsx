import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import type { WorkPool } from "@/api/work-pools";
import { createFakeWorkPoolWorker } from "@/mocks";
import { WorkPoolDetails } from "./work-pool-details";

const mockWorkers = [
	createFakeWorkPoolWorker({
		name: "worker-1",
		last_heartbeat_time: "2024-01-15T14:30:00Z",
	}),
	createFakeWorkPoolWorker({
		name: "worker-2",
		last_heartbeat_time: "2024-01-15T14:00:00Z",
	}),
];

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
			properties: {
				image: {
					type: "string",
					default: "python:3.9",
					title: "Docker Image",
					description: "The Docker image to use",
				},
			},
		},
	},
};

const server = setupServer(
	http.post(buildApiUrl("/work_pools/test-work-pool/workers/filter"), () => {
		return HttpResponse.json(mockWorkers);
	}),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const createWrapper = () => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: {
				retry: false,
			},
		},
	});
	const Wrapper = ({ children }: { children: React.ReactNode }) => (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);
	Wrapper.displayName = "TestWrapper";
	return Wrapper;
};

describe("WorkPoolDetails", () => {
	it("renders basic work pool information", async () => {
		render(<WorkPoolDetails workPool={mockWorkPool} />, {
			wrapper: createWrapper(),
		});

		// Wait for the workers data to load
		await waitFor(() => {
			expect(screen.getByText("A test work pool")).toBeInTheDocument();
		});

		expect(screen.getByText("Docker")).toBeInTheDocument();
		expect(screen.getByText("10")).toBeInTheDocument(); // concurrency limit
		// Check that we have formatted dates for created/updated
		const formattedDates = screen.getAllByText("over 1 year ago");
		expect(formattedDates.length).toBeGreaterThan(0);
	});

	it("renders job template configuration when present", async () => {
		render(<WorkPoolDetails workPool={mockWorkPool} />, {
			wrapper: createWrapper(),
		});

		// Wait for component to render
		await waitFor(() => {
			expect(screen.getByText("Base Job Configuration")).toBeInTheDocument();
		});
	});

	it("hides job template when not present", async () => {
		const workPoolWithoutTemplate = {
			...mockWorkPool,
			base_job_template: undefined,
		};

		render(<WorkPoolDetails workPool={workPoolWithoutTemplate} />, {
			wrapper: createWrapper(),
		});

		// Wait for component to render
		await waitFor(() => {
			expect(screen.getByText("A test work pool")).toBeInTheDocument();
		});

		expect(
			screen.queryByText("Base Job Configuration"),
		).not.toBeInTheDocument();
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

	it("handles missing optional fields gracefully", async () => {
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

		// Wait for component to render and check for unlimited concurrency limit
		await waitFor(() => {
			expect(screen.getByText("Unlimited")).toBeInTheDocument();
		});

		// Description should be hidden when not present
		expect(screen.queryByText("Description")).not.toBeInTheDocument();
	});
});
