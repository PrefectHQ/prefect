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
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// Mock navigator.clipboard
const mockWriteText = vi.fn().mockImplementation(() => Promise.resolve());
Object.assign(navigator, {
	clipboard: {
		writeText: mockWriteText,
	},
});

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
	it("copies worker ID to clipboard", async () => {
		const user = userEvent.setup();

		renderWithQueryClient(
			<WorkerMenu worker={mockWorker} workPoolName="test-pool" />,
		);

		// Open the dropdown menu
		const menuButton = screen.getByRole("button");
		await user.click(menuButton);

		// Click copy ID
		const copyButton = screen.getByText("Copy ID");
		await user.click(copyButton);

		expect(mockWriteText).toHaveBeenCalledWith(mockWorker.id);
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
		const deleteButton = screen.getByText("Delete");
		await user.click(deleteButton);

		// Should show confirmation dialog
		await waitFor(() => {
			expect(screen.getByText("Delete Worker")).toBeInTheDocument();
		});

		expect(
			screen.getByText(
				`Are you sure you want to delete the worker "${mockWorker.name}"?`,
			),
		).toBeInTheDocument();
	});

	it("deletes worker after confirmation", async () => {
		const user = userEvent.setup();
		const onWorkerDeleted = vi.fn();

		renderWithQueryClient(
			<WorkerMenu
				worker={mockWorker}
				workPoolName="test-pool"
				onWorkerDeleted={onWorkerDeleted}
			/>,
		);

		// Open the dropdown menu
		const menuButton = screen.getByRole("button");
		await user.click(menuButton);

		// Click delete
		const deleteButton = screen.getByText("Delete");
		await user.click(deleteButton);

		// Wait for dialog to appear
		await waitFor(() => {
			expect(screen.getByText("Delete Worker")).toBeInTheDocument();
		});

		// Type the worker name to confirm
		const confirmInput = screen.getByRole("textbox");
		await user.type(confirmInput, mockWorker.name);

		// Click delete button in dialog
		const confirmDeleteButton = screen.getByRole("button", { name: /delete/i });
		await user.click(confirmDeleteButton);

		// Wait for deletion to complete
		await waitFor(() => {
			expect(onWorkerDeleted).toHaveBeenCalled();
		});
	});
});
