import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import * as workPoolsApi from "@/api/work-pools";

import { WorkerMonitoring } from "./worker-monitoring";

// Mock the API
vi.mock("@/api/work-pools", () => ({
	buildListWorkPoolWorkersQuery: vi.fn(),
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
	return ({ children }: { children: React.ReactNode }) => (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);
};

describe("WorkerMonitoring", () => {
	it("shows worker monitoring with last polled time when workers exist", async () => {
		const mockWorkers = [
			{
				id: "worker1",
				name: "Worker 1",
				last_heartbeat_time: "2024-01-15T10:30:00Z",
			},
			{
				id: "worker2",
				name: "Worker 2",
				last_heartbeat_time: "2024-01-15T10:25:00Z",
			},
		];

		vi.mocked(workPoolsApi.buildListWorkPoolWorkersQuery).mockReturnValue({
			queryKey: ["work-pools", "workers", "test-pool"],
			queryFn: () => Promise.resolve(mockWorkers),
			refetchInterval: 30000,
		});

		render(<WorkerMonitoring workPoolName="test-pool" />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByText("Worker Monitoring")).toBeInTheDocument();
		expect(screen.getByText("Last Polled:")).toBeInTheDocument();
		// Shows the most recent heartbeat
		expect(screen.getByText("2024-01-15T10:30:00Z")).toBeInTheDocument();
	});

	it("does not render when no workers exist", async () => {
		vi.mocked(workPoolsApi.buildListWorkPoolWorkersQuery).mockReturnValue({
			queryKey: ["work-pools", "workers", "test-pool"],
			queryFn: () => Promise.resolve([]),
			refetchInterval: 30000,
		});

		const { container } = render(
			<WorkerMonitoring workPoolName="test-pool" />,
			{
				wrapper: createWrapper(),
			},
		);

		expect(container.firstChild).toBeNull();
	});

	it("shows no recent activity when workers have no heartbeat times", async () => {
		const mockWorkers = [
			{
				id: "worker1",
				name: "Worker 1",
				last_heartbeat_time: null,
			},
		];

		vi.mocked(workPoolsApi.buildListWorkPoolWorkersQuery).mockReturnValue({
			queryKey: ["work-pools", "workers", "test-pool"],
			queryFn: () => Promise.resolve(mockWorkers),
			refetchInterval: 30000,
		});

		render(<WorkerMonitoring workPoolName="test-pool" />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByText("Worker Monitoring")).toBeInTheDocument();
		expect(screen.getByText("No recent worker activity")).toBeInTheDocument();
	});

	it("applies custom className", async () => {
		const mockWorkers = [
			{
				id: "worker1",
				name: "Worker 1",
				last_heartbeat_time: "2024-01-15T10:30:00Z",
			},
		];

		vi.mocked(workPoolsApi.buildListWorkPoolWorkersQuery).mockReturnValue({
			queryKey: ["work-pools", "workers", "test-pool"],
			queryFn: () => Promise.resolve(mockWorkers),
			refetchInterval: 30000,
		});

		const { container } = render(
			<WorkerMonitoring workPoolName="test-pool" className="custom-class" />,
			{ wrapper: createWrapper() },
		);

		expect(container.firstChild).toHaveClass("custom-class");
	});
});
