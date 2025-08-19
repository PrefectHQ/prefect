import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { buildApiUrl, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { toast } from "sonner";
import { describe, expect, it, vi } from "vitest";
import { createFakeWorkPoolQueue } from "@/mocks";
import { DeleteWorkPoolQueueDialog } from "./delete-work-pool-queue-dialog";

// Mock toast
vi.mock("sonner", () => ({
	toast: {
		success: vi.fn(),
		error: vi.fn(),
	},
}));

// Mock the delete confirmation dialog
vi.mock("@/components/ui/delete-confirmation-dialog", () => ({
	DeleteConfirmationDialog: vi.fn(
		({
			isOpen,
			title,
			description,
			confirmText,
			isLoading,
			loadingText,
			onConfirm,
			onClose,
		}: {
			isOpen: boolean;
			title: string;
			description: string;
			confirmText: string;
			isLoading: boolean;
			loadingText: string;
			onConfirm: () => void;
			onClose: () => void;
		}) => (
			<div data-testid="delete-confirmation-dialog">
				{isOpen && (
					<div>
						<h2>{title}</h2>
						<p>{description}</p>
						<span>Confirm text: {confirmText}</span>
						<button type="button" onClick={onConfirm} disabled={isLoading}>
							{isLoading ? loadingText : "Delete"}
						</button>
						<button type="button" onClick={onClose}>
							Cancel
						</button>
					</div>
				)}
			</div>
		),
	),
}));

describe("DeleteWorkPoolQueueDialog", () => {
	const createTestQueryClient = () => {
		return new QueryClient({
			defaultOptions: {
				queries: {
					retry: false,
				},
				mutations: {
					retry: false,
				},
			},
		});
	};

	const renderWithClient = (component: React.ReactElement) => {
		const queryClient = createTestQueryClient();
		return render(
			<QueryClientProvider client={queryClient}>
				{component}
			</QueryClientProvider>,
		);
	};

	const defaultProps = {
		queue: createFakeWorkPoolQueue({
			name: "test-queue",
			work_pool_name: "test-pool",
		}),
		open: true,
		onOpenChange: vi.fn(),
		onDeleted: vi.fn(),
	};

	it("renders delete confirmation dialog when open", () => {
		renderWithClient(<DeleteWorkPoolQueueDialog {...defaultProps} />);

		expect(
			screen.getByTestId("delete-confirmation-dialog"),
		).toBeInTheDocument();
		expect(screen.getByText("Delete Work Pool Queue")).toBeInTheDocument();
		expect(
			screen.getByText(
				'Are you sure you want to delete the work pool queue "test-queue"? This action cannot be undone.',
			),
		).toBeInTheDocument();
		expect(screen.getByText("Confirm text: test-queue")).toBeInTheDocument();
	});

	it("does not render dialog when closed", () => {
		renderWithClient(
			<DeleteWorkPoolQueueDialog {...defaultProps} open={false} />,
		);

		const dialog = screen.queryByText("Delete Work Pool Queue");
		expect(dialog).not.toBeInTheDocument();
	});

	it("calls DELETE API to delete queue", async () => {
		let deleteRequestMade = false;

		// Mock the API endpoint
		server.use(
			http.delete(
				buildApiUrl("/work_pools/test-pool/queues/test-queue"),
				() => {
					deleteRequestMade = true;
					return HttpResponse.json({});
				},
			),
		);

		renderWithClient(<DeleteWorkPoolQueueDialog {...defaultProps} />);

		const deleteButton = screen.getByRole("button", { name: "Delete" });
		fireEvent.click(deleteButton);

		await waitFor(() => {
			expect(deleteRequestMade).toBe(true);
		});
	});

	it("shows success toast and calls callbacks on successful delete", async () => {
		const onDeleted = vi.fn();
		const onOpenChange = vi.fn();

		// Mock successful API response
		server.use(
			http.delete(
				buildApiUrl("/work_pools/test-pool/queues/test-queue"),
				() => {
					return HttpResponse.json({});
				},
			),
		);

		renderWithClient(
			<DeleteWorkPoolQueueDialog
				{...defaultProps}
				onDeleted={onDeleted}
				onOpenChange={onOpenChange}
			/>,
		);

		const deleteButton = screen.getByRole("button", { name: "Delete" });
		fireEvent.click(deleteButton);

		await waitFor(() => {
			expect(toast.success).toHaveBeenCalledWith(
				"Work pool queue deleted successfully",
			);
			expect(onDeleted).toHaveBeenCalled();
			expect(onOpenChange).toHaveBeenCalledWith(false);
		});
	});

	it("shows error toast on delete failure", async () => {
		// Mock API to return error
		server.use(
			http.delete(
				buildApiUrl("/work_pools/test-pool/queues/test-queue"),
				() => {
					return HttpResponse.json(
						{ error: "Failed to delete" },
						{ status: 500 },
					);
				},
			),
		);

		renderWithClient(<DeleteWorkPoolQueueDialog {...defaultProps} />);

		const deleteButton = screen.getByRole("button", { name: "Delete" });
		fireEvent.click(deleteButton);

		await waitFor(() => {
			expect(toast.error).toHaveBeenCalledWith(
				"Failed to delete work pool queue",
			);
		});
	});

	it("calls onOpenChange when cancel is clicked", () => {
		const onOpenChange = vi.fn();

		renderWithClient(
			<DeleteWorkPoolQueueDialog
				{...defaultProps}
				onOpenChange={onOpenChange}
			/>,
		);

		const cancelButton = screen.getByRole("button", { name: "Cancel" });
		fireEvent.click(cancelButton);

		expect(onOpenChange).toHaveBeenCalledWith(false);
	});
});
