import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import {
	afterAll,
	afterEach,
	beforeAll,
	describe,
	expect,
	it,
	vi,
} from "vitest";
import { createFakeWorkPoolWorker } from "@/mocks/create-fake-work-pool-worker";
import { WorkerMenu } from "./worker-menu";

const mockWorker = createFakeWorkPoolWorker({
	name: "test-worker",
	work_pool_id: "test-pool-id",
});

const server = setupServer(
	http.delete("/api/work_pools/test-pool/workers/test-worker", () => {
		return HttpResponse.json({});
	}),
);

beforeAll(() => server.listen());
afterEach(() => {
	server.resetHandlers();
	vi.clearAllMocks();
});
afterAll(() => server.close());

const renderWithQueryClient = (component: React.ReactElement) => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: { retry: false },
			mutations: { retry: false },
		},
	});

	return render(
		<QueryClientProvider client={queryClient}>{component}</QueryClientProvider>,
	);
};

describe("WorkerMenu", () => {
	it("renders menu with copy and delete options", async () => {
		const user = userEvent.setup();

		renderWithQueryClient(
			<WorkerMenu worker={mockWorker} workPoolName="test-pool" />,
		);

		// Open the dropdown menu
		const menuButton = screen.getByRole("button");
		await user.click(menuButton);

		// Verify menu items are present
		expect(await screen.findByText("Copy ID")).toBeInTheDocument();
		expect(await screen.findByText("Delete")).toBeInTheDocument();
	});

	it("shows delete confirmation dialog", async () => {
		const user = userEvent.setup();

		renderWithQueryClient(
			<WorkerMenu worker={mockWorker} workPoolName="test-pool" />,
		);

		// Open the dropdown menu
		const menuButton = screen.getByRole("button");
		await user.click(menuButton);

		// Click delete
		const deleteButton = await screen.findByText("Delete");
		await user.click(deleteButton);

		// Should show confirmation dialog
		await waitFor(() => {
			expect(screen.getByText("Delete Worker")).toBeInTheDocument();
		});

		// Check for confirmation text (look for partial match as text might be split)
		expect(
			screen.getByText(/This action cannot be undone/),
		).toBeInTheDocument();
	});

	it("cancels deletion when cancel is clicked", async () => {
		const user = userEvent.setup();

		renderWithQueryClient(
			<WorkerMenu worker={mockWorker} workPoolName="test-pool" />,
		);

		// Open the dropdown menu
		const menuButton = screen.getByRole("button");
		await user.click(menuButton);

		// Click delete
		const deleteButton = await screen.findByText("Delete");
		await user.click(deleteButton);

		// Wait for dialog to appear
		await waitFor(() => {
			expect(screen.getByText("Delete Worker")).toBeInTheDocument();
		});

		// Click cancel
		const cancelButton = screen.getByRole("button", { name: "Cancel" });
		await user.click(cancelButton);

		// Dialog should disappear
		await waitFor(() => {
			expect(screen.queryByText("Delete Worker")).not.toBeInTheDocument();
		});
	});
});
