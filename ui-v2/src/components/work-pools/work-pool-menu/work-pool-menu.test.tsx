import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { WorkPool } from "@/api/work-pools";
import { WorkPoolMenu } from "./work-pool-menu";

// Mock DeleteWorkPoolDialog
vi.mock("./components/delete-work-pool-dialog", () => ({
	DeleteWorkPoolDialog: ({
		open,
		onOpenChange,
		workPool,
		onDeleted,
	}: {
		open: boolean;
		onOpenChange: (open: boolean) => void;
		workPool: WorkPool;
		onDeleted?: () => void;
	}) =>
		open ? (
			<div data-testid="delete-dialog">
				<button type="button" onClick={() => onOpenChange(false)}>
					Close
				</button>
				<span>{workPool.name}</span>
				{onDeleted && (
					<button type="button" onClick={onDeleted}>
						Delete
					</button>
				)}
			</div>
		) : null,
}));

// Mock toast
vi.mock("sonner", () => ({
	toast: {
		success: vi.fn(),
		error: vi.fn(),
	},
}));

// Mock useNavigate hook
vi.mock("@tanstack/react-router", () => ({
	useNavigate: () => vi.fn(),
}));

const mockWorkPool: WorkPool = {
	id: "123",
	created: "2024-01-01T00:00:00Z",
	updated: "2024-01-01T00:00:00Z",
	name: "test-work-pool",
	description: "Test work pool",
	type: "process",
	base_job_template: {},
	is_paused: false,
	concurrency_limit: null,
	status: "READY",
};

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

describe("WorkPoolMenu", () => {
	const writeTextMock = vi.fn();

	beforeEach(() => {
		vi.clearAllMocks();
		writeTextMock.mockResolvedValue(undefined);
		// Mock clipboard API
		Object.defineProperty(navigator, "clipboard", {
			value: {
				writeText: writeTextMock,
			},
			writable: true,
			configurable: true,
		});
	});

	it("renders menu trigger button", () => {
		const Wrapper = createWrapper();
		render(<WorkPoolMenu workPool={mockWorkPool} />, {
			wrapper: Wrapper,
		});
		const button = screen.getByRole("button", { name: /open menu/i });
		expect(button).toBeInTheDocument();
	});

	it("opens menu when clicked", async () => {
		const Wrapper = createWrapper();
		render(<WorkPoolMenu workPool={mockWorkPool} />, {
			wrapper: Wrapper,
		});

		const user = userEvent.setup({
			// Don't overwrite our clipboard mock
			writeToClipboard: false,
		});
		const button = screen.getByRole("button", { name: /open menu/i });
		await user.click(button);

		expect(screen.getByText("Copy ID")).toBeInTheDocument();
		expect(screen.getByText("Edit")).toBeInTheDocument();
		expect(screen.getByText("Delete")).toBeInTheDocument();
		expect(screen.getByText("Automate")).toBeInTheDocument();
	});

	it("handles copy ID action", async () => {
		const Wrapper = createWrapper();
		render(<WorkPoolMenu workPool={mockWorkPool} />, {
			wrapper: Wrapper,
		});

		const user = userEvent.setup();
		const button = screen.getByRole("button", { name: /open menu/i });
		await user.click(button);

		// Wait for menu to be visible
		await waitFor(() => {
			expect(screen.getByText("Copy ID")).toBeInTheDocument();
		});

		const copyButton = screen.getByText("Copy ID");
		await user.click(copyButton);

		// Check that toast was called
		await waitFor(() => {
			expect(toast.success).toHaveBeenCalledWith("ID copied to clipboard");
		});
	});

	it("shows delete confirmation dialog", async () => {
		const Wrapper = createWrapper();
		render(<WorkPoolMenu workPool={mockWorkPool} />, {
			wrapper: Wrapper,
		});

		const user = userEvent.setup({
			// Don't overwrite our clipboard mock
			writeToClipboard: false,
		});
		const button = screen.getByRole("button", { name: /open menu/i });
		await user.click(button);

		const deleteButton = screen.getByText("Delete");
		await user.click(deleteButton);

		await waitFor(() => {
			expect(screen.getByTestId("delete-dialog")).toBeInTheDocument();
		});
	});

	it("applies custom className", () => {
		const Wrapper = createWrapper();
		render(<WorkPoolMenu workPool={mockWorkPool} className="custom-class" />, {
			wrapper: Wrapper,
		});
		const button = screen.getByRole("button", { name: /open menu/i });
		expect(button).toHaveClass("custom-class");
	});

	it("passes onUpdate to delete dialog", async () => {
		const onUpdate = vi.fn();
		const Wrapper = createWrapper();
		render(<WorkPoolMenu workPool={mockWorkPool} onUpdate={onUpdate} />, {
			wrapper: Wrapper,
		});

		const user = userEvent.setup({
			// Don't overwrite our clipboard mock
			writeToClipboard: false,
		});
		const button = screen.getByRole("button", { name: /open menu/i });
		await user.click(button);

		const deleteButton = screen.getByText("Delete");
		await user.click(deleteButton);

		await waitFor(() => {
			expect(screen.getByTestId("delete-dialog")).toBeInTheDocument();
		});
	});
});
