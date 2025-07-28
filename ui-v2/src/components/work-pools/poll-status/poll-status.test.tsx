import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import * as workPoolsApi from "@/api/work-pools";

import { PollStatus } from "./poll-status";

// Mock the API
vi.mock("@/api/work-pools", () => ({
	buildListWorkPoolWorkersQuery: vi.fn(() => ({
		queryKey: ["work-pools", "workers", "test-pool"] as const,
		queryFn: () => Promise.resolve([]),
		refetchInterval: 30000,
	})),
}));

// Mock the FormattedDate component
vi.mock("@/components/ui/formatted-date", () => ({
	FormattedDate: ({ date }: { date: string }) => <span>{date}</span>,
}));

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

describe("PollStatus", () => {
	it("shows poll status with last polled time when workers exist", () => {
		const mockWorkers = [
			{
				id: "worker1",
				name: "Worker 1",
				created: "2024-01-15T10:00:00Z",
				updated: "2024-01-15T10:30:00Z",
				work_pool_id: "test-pool",
				last_heartbeat_time: "2024-01-15T10:30:00Z",
				heartbeat_interval_seconds: 30,
				status: "ONLINE" as const,
			},
			{
				id: "worker2",
				name: "Worker 2",
				created: "2024-01-15T10:00:00Z",
				updated: "2024-01-15T10:25:00Z",
				work_pool_id: "test-pool",
				last_heartbeat_time: "2024-01-15T10:25:00Z",
				heartbeat_interval_seconds: 30,
				status: "ONLINE" as const,
			},
		];

		vi.mocked(workPoolsApi.buildListWorkPoolWorkersQuery).mockReturnValue({
			queryKey: ["work-pools", "workers", "test-pool"],
			queryFn: () => Promise.resolve(mockWorkers),
			refetchInterval: 30000,
		});

		render(<PollStatus workPoolName="test-pool" />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByText("Poll Status")).toBeInTheDocument();
		expect(screen.getByText("Last Polled:")).toBeInTheDocument();
		// Shows the most recent heartbeat
		expect(screen.getByText("2024-01-15T10:30:00Z")).toBeInTheDocument();
	});

	it("does not render when no workers exist", () => {
		vi.mocked(workPoolsApi.buildListWorkPoolWorkersQuery).mockReturnValue({
			queryKey: ["work-pools", "workers", "test-pool"],
			queryFn: () => Promise.resolve([]),
			refetchInterval: 30000,
		});

		const { container } = render(<PollStatus workPoolName="test-pool" />, {
			wrapper: createWrapper(),
		});

		expect(container.firstChild).toBeNull();
	});

	it("shows no recent activity when workers have no heartbeat times", () => {
		const mockWorkers = [
			{
				id: "worker1",
				name: "Worker 1",
				created: "2024-01-15T10:00:00Z",
				updated: "2024-01-15T10:25:00Z",
				work_pool_id: "test-pool",
				last_heartbeat_time: null,
				heartbeat_interval_seconds: 30,
				status: "OFFLINE" as const,
			},
		];

		vi.mocked(workPoolsApi.buildListWorkPoolWorkersQuery).mockReturnValue({
			queryKey: ["work-pools", "workers", "test-pool"],
			queryFn: () => Promise.resolve(mockWorkers),
			refetchInterval: 30000,
		});

		render(<PollStatus workPoolName="test-pool" />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByText("Poll Status")).toBeInTheDocument();
		expect(screen.getByText("No recent worker activity")).toBeInTheDocument();
	});

	it("applies custom className", () => {
		const mockWorkers = [
			{
				id: "worker1",
				name: "Worker 1",
				created: "2024-01-15T10:00:00Z",
				updated: "2024-01-15T10:30:00Z",
				work_pool_id: "test-pool",
				last_heartbeat_time: "2024-01-15T10:30:00Z",
				heartbeat_interval_seconds: 30,
				status: "ONLINE" as const,
			},
		];

		vi.mocked(workPoolsApi.buildListWorkPoolWorkersQuery).mockReturnValue({
			queryKey: ["work-pools", "workers", "test-pool"],
			queryFn: () => Promise.resolve(mockWorkers),
			refetchInterval: 30000,
		});

		const { container } = render(
			<PollStatus workPoolName="test-pool" className="custom-class" />,
			{ wrapper: createWrapper() },
		);

		expect(container.firstChild).toHaveClass("custom-class");
	});
});
