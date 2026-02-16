import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { WorkPool } from "@/api/work-pools";
import { TooltipProvider } from "@/components/ui/tooltip";
import { WorkPoolToggle } from "./work-pool-toggle";

// Mock toast
vi.mock("sonner", () => ({
	toast: {
		success: vi.fn(),
		error: vi.fn(),
	},
}));

// Mock the mutation hooks to prevent actual API calls
vi.mock("@/api/work-pools", () => ({
	usePauseWorkPool: () => ({
		pauseWorkPool: vi.fn(),
		isPending: false,
	}),
	useResumeWorkPool: () => ({
		resumeWorkPool: vi.fn(),
		isPending: false,
	}),
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

	const Wrapper = ({ children }: { children: React.ReactNode }) => (
		<QueryClientProvider client={queryClient}>
			<TooltipProvider>{children}</TooltipProvider>
		</QueryClientProvider>
	);
	Wrapper.displayName = "TestWrapper";
	return Wrapper;
};

describe("WorkPoolToggle", () => {
	it("shows switch as checked when work pool is active", () => {
		const Wrapper = createWrapper();
		render(<WorkPoolToggle workPool={mockWorkPoolReady} />, {
			wrapper: Wrapper,
		});

		const switchElement = screen.getByRole("switch");
		expect(switchElement).toHaveAttribute("aria-checked", "true");
	});

	it("shows switch as unchecked when work pool is paused", () => {
		const Wrapper = createWrapper();
		render(<WorkPoolToggle workPool={mockWorkPoolPaused} />, {
			wrapper: Wrapper,
		});

		const switchElement = screen.getByRole("switch");
		expect(switchElement).toHaveAttribute("aria-checked", "false");
	});

	it("has correct aria-label for pause action", () => {
		const Wrapper = createWrapper();
		render(<WorkPoolToggle workPool={mockWorkPoolReady} />, {
			wrapper: Wrapper,
		});

		const switchElement = screen.getByRole("switch");
		expect(switchElement).toHaveAttribute("aria-label", "Pause work pool");
	});

	it("has correct aria-label for resume action", () => {
		const Wrapper = createWrapper();
		render(<WorkPoolToggle workPool={mockWorkPoolPaused} />, {
			wrapper: Wrapper,
		});

		const switchElement = screen.getByRole("switch");
		expect(switchElement).toHaveAttribute("aria-label", "Resume work pool");
	});

	it("is not disabled by default", () => {
		const Wrapper = createWrapper();
		render(<WorkPoolToggle workPool={mockWorkPoolReady} />, {
			wrapper: Wrapper,
		});

		const switchElement = screen.getByRole("switch");
		expect(switchElement).not.toBeDisabled();
	});

	it("renders tooltip trigger", () => {
		const Wrapper = createWrapper();
		render(<WorkPoolToggle workPool={mockWorkPoolReady} />, {
			wrapper: Wrapper,
		});

		const tooltipTrigger = document.querySelector(
			"[data-slot='tooltip-trigger']",
		);
		expect(tooltipTrigger).toBeInTheDocument();

		const switchElement = screen.getByRole("switch");
		expect(switchElement).toBeInTheDocument();
		expect(switchElement).toHaveAttribute("data-slot", "switch");
	});
});
