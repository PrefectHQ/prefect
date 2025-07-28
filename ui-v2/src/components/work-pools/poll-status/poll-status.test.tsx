import { render, screen } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it, vi } from "vitest";

import { PollStatus } from "./poll-status";

// Mock the FormattedDate component
vi.mock("@/components/ui/formatted-date", () => ({
	FormattedDate: ({ date }: { date: string }) => (
		<span data-testid="formatted-date">{date}</span>
	),
}));

const mockWorkers = [
	{
		id: "worker1",
		name: "Worker 1",
		created: "2024-01-15T10:00:00Z",
		updated: "2024-01-15T10:30:00Z",
		work_pool_id: "test-pool",
		last_heartbeat_time: "2024-01-15T10:30:00Z",
		heartbeat_interval_seconds: 30,
		status: "ONLINE",
	},
];

describe("PollStatus", () => {
	it("renders null when no workers exist", async () => {
		// Default handler already returns empty array, so no override needed
		const { container } = render(<PollStatus workPoolName="test-pool" />, {
			wrapper: createWrapper(),
		});

		// Wait for suspense to resolve and check that nothing is rendered
		await new Promise((resolve) => setTimeout(resolve, 0));
		expect(container.firstChild).toBeNull();
	});

	it("renders poll status when workers exist", async () => {
		// Override handler to return workers with heartbeat data
		server.use(
			http.post(buildApiUrl("/work_pools/:name/workers/filter"), () => {
				return HttpResponse.json(mockWorkers);
			}),
		);

		render(<PollStatus workPoolName="test-pool" />, {
			wrapper: createWrapper(),
		});

		// Wait for suspense to resolve
		await screen.findByText("Poll Status");

		expect(screen.getByText("Poll Status")).toBeInTheDocument();
		expect(screen.getByText("Last Polled:")).toBeInTheDocument();
		expect(screen.getByTestId("formatted-date")).toBeInTheDocument();
	});
});
