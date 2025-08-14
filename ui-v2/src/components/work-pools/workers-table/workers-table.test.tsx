import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { createFakeWorkPoolWorkers } from "@/mocks/create-fake-work-pool-worker";
import { WorkersTable } from "./workers-table";

const mockWorkers = createFakeWorkPoolWorkers(3, {
	work_pool_id: "test-pool-id",
});

const mockWorkersOnline = [
	...mockWorkers,
	{
		...mockWorkers[0],
		name: "online-worker",
		status: "ONLINE" as const,
	},
];

const server = setupServer(
	http.post("/api/work_pools/test-pool/workers/filter", () => {
		return HttpResponse.json(mockWorkersOnline);
	}),
	http.post("/api/work_pools/empty-pool/workers/filter", () => {
		return HttpResponse.json([]);
	}),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const renderWithQueryClient = (component: React.ReactElement) => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: { retry: false },
		},
	});

	return render(
		<QueryClientProvider client={queryClient}>{component}</QueryClientProvider>,
	);
};

describe("WorkersTable", () => {
	it("renders workers list correctly", async () => {
		renderWithQueryClient(<WorkersTable workPoolName="test-pool" />);

		await waitFor(() => {
			expect(screen.getByText("online-worker")).toBeInTheDocument();
		});

		expect(screen.getByText("4 workers")).toBeInTheDocument();
	});

	it("filters workers based on search query", async () => {
		const user = userEvent.setup();

		renderWithQueryClient(<WorkersTable workPoolName="test-pool" />);

		await waitFor(() => {
			expect(screen.getByText("online-worker")).toBeInTheDocument();
		});

		const searchInput = screen.getByPlaceholderText("Search workers...");
		await user.type(searchInput, "online");

		await waitFor(() => {
			expect(screen.getByText("1 of 4 workers")).toBeInTheDocument();
		});

		expect(screen.getByText("online-worker")).toBeInTheDocument();
		expect(screen.queryByText(mockWorkers[0].name)).not.toBeInTheDocument();
	});

	it("shows empty state when no workers", async () => {
		renderWithQueryClient(<WorkersTable workPoolName="empty-pool" />);

		await waitFor(() => {
			expect(screen.getByText("No workers running")).toBeInTheDocument();
		});

		expect(screen.getByText("0 workers")).toBeInTheDocument();
		expect(
			screen.getByText('prefect worker start --pool "empty-pool"'),
		).toBeInTheDocument();
	});

	it("shows 'no results' when search has no matches", async () => {
		const user = userEvent.setup();

		renderWithQueryClient(<WorkersTable workPoolName="test-pool" />);

		await waitFor(() => {
			expect(screen.getByText("4 workers")).toBeInTheDocument();
		});

		const searchInput = screen.getByPlaceholderText("Search workers...");
		await user.type(searchInput, "nonexistent-worker");

		await waitFor(() => {
			expect(screen.getByText("No workers found")).toBeInTheDocument();
		});

		expect(
			screen.getByText("No workers match your search criteria."),
		).toBeInTheDocument();
		expect(screen.getByText("0 of 4 workers")).toBeInTheDocument();
	});

	it("clears search filters", async () => {
		const user = userEvent.setup();

		renderWithQueryClient(<WorkersTable workPoolName="test-pool" />);

		await waitFor(() => {
			expect(screen.getByText("4 workers")).toBeInTheDocument();
		});

		const searchInput = screen.getByPlaceholderText("Search workers...");
		await user.type(searchInput, "online");

		await waitFor(() => {
			expect(screen.getByText("1 of 4 workers")).toBeInTheDocument();
		});

		const clearButton = screen.getByText("Clear filters");
		await user.click(clearButton);

		await waitFor(() => {
			expect(screen.getByText("4 workers")).toBeInTheDocument();
		});

		expect(searchInput).toHaveValue("");
	});
});
