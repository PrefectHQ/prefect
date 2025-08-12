import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { WorkPool } from "@/api/work-pools";
import { TooltipProvider } from "@/components/ui/tooltip";
import { WorkPoolToggle } from "./work-pool-toggle";

// Mock the API hooks
vi.mock("@/api/work-pools", () => ({
	usePauseWorkPool: vi.fn(),
	useResumeWorkPool: vi.fn(),
}));

// Mock toast
vi.mock("sonner", () => ({
	toast: {
		success: vi.fn(),
		error: vi.fn(),
	},
}));

const mockWorkPoolReady: WorkPool = {
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

const mockWorkPoolPaused: WorkPool = {
	...mockWorkPoolReady,
	status: "PAUSED",
	is_paused: true,
};

const createWrapper = () => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: { retry: false },
			mutations: { retry: false },
		},
	});

	return ({ children }: { children: React.ReactNode }) => (
		<QueryClientProvider client={queryClient}>
			<TooltipProvider>{children}</TooltipProvider>
		</QueryClientProvider>
	);
};

describe("WorkPoolToggle", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("shows switch as checked when work pool is active", async () => {
		const { usePauseWorkPool, useResumeWorkPool } = vi.mocked(
			await import("@/api/work-pools"),
		);
		usePauseWorkPool.mockReturnValue({
			pauseWorkPool: vi.fn(),
			isPending: false,
		} as any);
		useResumeWorkPool.mockReturnValue({
			resumeWorkPool: vi.fn(),
			isPending: false,
		} as any);

		const Wrapper = createWrapper();
		render(<WorkPoolToggle workPool={mockWorkPoolReady} />, {
			wrapper: Wrapper,
		});

		const switchElement = screen.getByRole("switch");
		expect(switchElement).toHaveAttribute("aria-checked", "true");
	});

	it("shows switch as unchecked when work pool is paused", async () => {
		const { usePauseWorkPool, useResumeWorkPool } = vi.mocked(
			await import("@/api/work-pools"),
		);
		usePauseWorkPool.mockReturnValue({
			pauseWorkPool: vi.fn(),
			isPending: false,
		} as any);
		useResumeWorkPool.mockReturnValue({
			resumeWorkPool: vi.fn(),
			isPending: false,
		} as any);

		const Wrapper = createWrapper();
		render(<WorkPoolToggle workPool={mockWorkPoolPaused} />, {
			wrapper: Wrapper,
		});

		const switchElement = screen.getByRole("switch");
		expect(switchElement).toHaveAttribute("aria-checked", "false");
	});

	it("calls pauseWorkPool when toggling from active to paused", async () => {
		const pauseWorkPoolMock = vi.fn((_, options) => {
			options.onSuccess();
		});
		const { usePauseWorkPool, useResumeWorkPool } = vi.mocked(
			await import("@/api/work-pools"),
		);
		usePauseWorkPool.mockReturnValue({
			pauseWorkPool: pauseWorkPoolMock,
			isPending: false,
		} as any);
		useResumeWorkPool.mockReturnValue({
			resumeWorkPool: vi.fn(),
			isPending: false,
		} as any);

		const onUpdate = vi.fn();
		const Wrapper = createWrapper();
		render(
			<WorkPoolToggle workPool={mockWorkPoolReady} onUpdate={onUpdate} />,
			{
				wrapper: Wrapper,
			},
		);

		const user = userEvent.setup();
		const switchElement = screen.getByRole("switch");
		await user.click(switchElement);

		await waitFor(() => {
			expect(pauseWorkPoolMock).toHaveBeenCalledWith(
				"test-work-pool",
				expect.objectContaining({
					onSuccess: expect.any(Function),
					onError: expect.any(Function),
				}),
			);
			expect(toast.success).toHaveBeenCalledWith("Work pool paused");
			expect(onUpdate).toHaveBeenCalled();
		});
	});

	it("calls resumeWorkPool when toggling from paused to active", async () => {
		const resumeWorkPoolMock = vi.fn((_, options) => {
			options.onSuccess();
		});
		const { usePauseWorkPool, useResumeWorkPool } = vi.mocked(
			await import("@/api/work-pools"),
		);
		usePauseWorkPool.mockReturnValue({
			pauseWorkPool: vi.fn(),
			isPending: false,
		} as any);
		useResumeWorkPool.mockReturnValue({
			resumeWorkPool: resumeWorkPoolMock,
			isPending: false,
		} as any);

		const onUpdate = vi.fn();
		const Wrapper = createWrapper();
		render(
			<WorkPoolToggle workPool={mockWorkPoolPaused} onUpdate={onUpdate} />,
			{
				wrapper: Wrapper,
			},
		);

		const user = userEvent.setup();
		const switchElement = screen.getByRole("switch");
		await user.click(switchElement);

		await waitFor(() => {
			expect(resumeWorkPoolMock).toHaveBeenCalledWith(
				"test-work-pool",
				expect.objectContaining({
					onSuccess: expect.any(Function),
					onError: expect.any(Function),
				}),
			);
			expect(toast.success).toHaveBeenCalledWith("Work pool resumed");
			expect(onUpdate).toHaveBeenCalled();
		});
	});

	it("shows loading state during mutation", async () => {
		const { usePauseWorkPool, useResumeWorkPool } = vi.mocked(
			await import("@/api/work-pools"),
		);
		usePauseWorkPool.mockReturnValue({
			pauseWorkPool: vi.fn(),
			isPending: true,
		} as any);
		useResumeWorkPool.mockReturnValue({
			resumeWorkPool: vi.fn(),
			isPending: false,
		} as any);

		const Wrapper = createWrapper();
		render(<WorkPoolToggle workPool={mockWorkPoolReady} />, {
			wrapper: Wrapper,
		});

		const switchElement = screen.getByRole("switch");
		expect(switchElement).toBeDisabled();
	});

	it("handles errors gracefully", async () => {
		const pauseWorkPoolMock = vi.fn((_, options) => {
			options.onError();
		});
		const { usePauseWorkPool, useResumeWorkPool } = vi.mocked(
			await import("@/api/work-pools"),
		);
		usePauseWorkPool.mockReturnValue({
			pauseWorkPool: pauseWorkPoolMock,
			isPending: false,
		} as any);
		useResumeWorkPool.mockReturnValue({
			resumeWorkPool: vi.fn(),
			isPending: false,
		} as any);

		const Wrapper = createWrapper();
		render(<WorkPoolToggle workPool={mockWorkPoolReady} />, {
			wrapper: Wrapper,
		});

		const user = userEvent.setup();
		const switchElement = screen.getByRole("switch");
		await user.click(switchElement);

		await waitFor(() => {
			expect(toast.error).toHaveBeenCalledWith("Failed to pause work pool");
		});
	});
});