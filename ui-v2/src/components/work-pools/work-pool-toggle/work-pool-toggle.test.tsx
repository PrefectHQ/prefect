import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { setupServer } from "msw/node";
import { toast } from "sonner";
import {
	afterAll,
	afterEach,
	beforeAll,
	beforeEach,
	describe,
	expect,
	it,
	vi,
} from "vitest";
import type { WorkPool } from "@/api/work-pools";
import { TooltipProvider } from "@/components/ui/tooltip";
import { WorkPoolToggle } from "./work-pool-toggle";

// Setup MSW server
const server = setupServer();

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

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

	it("calls pauseWorkPool when toggling from active to paused", async () => {
		server.use(
			http.patch(buildApiUrl("/work_pools/:name"), () => {
				return HttpResponse.json({ ...mockWorkPoolReady, is_paused: true });
			}),
		);

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
			expect(toast.success).toHaveBeenCalledWith("Work pool paused");
			expect(onUpdate).toHaveBeenCalled();
		});
	});

	it("calls resumeWorkPool when toggling from paused to active", async () => {
		server.use(
			http.patch(buildApiUrl("/work_pools/:name"), () => {
				return HttpResponse.json({ ...mockWorkPoolPaused, is_paused: false });
			}),
		);

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
			expect(toast.success).toHaveBeenCalledWith("Work pool resumed");
			expect(onUpdate).toHaveBeenCalled();
		});
	});

	it("shows loading state during mutation", async () => {
		// Set up a slow response to test loading state
		server.use(
			http.patch(buildApiUrl("/work_pools/:name"), async () => {
				await new Promise((resolve) => setTimeout(resolve, 1000));
				return HttpResponse.json({ ...mockWorkPoolReady, is_paused: true });
			}),
		);

		const Wrapper = createWrapper();
		render(<WorkPoolToggle workPool={mockWorkPoolReady} />, {
			wrapper: Wrapper,
		});

		const user = userEvent.setup();
		const switchElement = screen.getByRole("switch");

		// Start the toggle action but don't wait for it
		const clickPromise = user.click(switchElement);

		// Check that switch gets disabled during loading
		await waitFor(() => {
			expect(switchElement).toBeDisabled();
		});

		// Clean up by waiting for the click to complete
		await clickPromise;
	});

	it("handles errors gracefully", async () => {
		server.use(
			http.patch(buildApiUrl("/work_pools/:name"), () => {
				return HttpResponse.json(
					{ detail: "Failed to pause work pool" },
					{ status: 500 },
				);
			}),
		);

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
