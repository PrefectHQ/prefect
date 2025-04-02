import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { toast } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createFakeWorkPool } from "@/mocks/create-fake-work-pool";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { WorkPoolPauseResumeToggle } from "./work-pool-pause-resume-toggle";

vi.mock("sonner", () => ({
	toast: {
		success: vi.fn(),
		error: vi.fn(),
	},
}));

describe("WorkPoolPauseResumeToggle", () => {
	const activeWorkPool = createFakeWorkPool({
		name: "active-work-pool",
		status: "READY",
		is_paused: false,
	});

	const pausedWorkPool = createFakeWorkPool({
		name: "paused-work-pool",
		status: "PAUSED",
		is_paused: true,
	});

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders the active state correctly", () => {
		render(<WorkPoolPauseResumeToggle workPool={activeWorkPool} />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByText("Active")).toBeInTheDocument();
		expect(screen.getByRole("switch")).toBeChecked();
	});

	it("renders the paused state correctly", () => {
		render(<WorkPoolPauseResumeToggle workPool={pausedWorkPool} />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByText("Paused")).toBeInTheDocument();
		expect(screen.getByRole("switch")).not.toBeChecked();
	});

	it("disables the switch while the API request is pending", async () => {
		server.use(
			http.patch(
				buildApiUrl(`/work_pools/${activeWorkPool.name}`),
				async () => {
					await new Promise((resolve) => setTimeout(resolve, 500));
					return HttpResponse.json({});
				},
			),
		);

		render(<WorkPoolPauseResumeToggle workPool={activeWorkPool} />, {
			wrapper: createWrapper(),
		});

		const toggle = screen.getByRole("switch", { name: /pause work pool/i });

		fireEvent.click(toggle);

		expect(toggle).toBeDisabled();

		await waitFor(() => {
			expect(toast.success).toHaveBeenCalled();
		});

		expect(toggle).toBeEnabled();
	});

	it("shows an error toast when the API call fails", async () => {
		const errorMessage = "Failed to update work pool status";

		server.use(
			http.patch(buildApiUrl(`/work_pools/${activeWorkPool.name}`), () => {
				return HttpResponse.json({ detail: errorMessage }, { status: 500 });
			}),
		);

		render(<WorkPoolPauseResumeToggle workPool={activeWorkPool} />, {
			wrapper: createWrapper(),
		});

		fireEvent.click(screen.getByRole("switch"));

		await waitFor(() => {
			expect(toast.error).toHaveBeenCalled();
		});
	});

	it("updates the UI state after successful API call to pause", async () => {
		server.use(
			http.patch(buildApiUrl(`/work_pools/${activeWorkPool.name}`), () => {
				return HttpResponse.json({});
			}),
		);

		render(<WorkPoolPauseResumeToggle workPool={activeWorkPool} />, {
			wrapper: createWrapper(),
		});

		// Initially should show Active
		expect(screen.getByText("Active")).toBeInTheDocument();

		// Toggle to pause
		fireEvent.click(screen.getByRole("switch"));

		// After successful API call, should show Paused
		await waitFor(() => {
			expect(screen.getByText("Paused")).toBeInTheDocument();
		});
	});

	it("updates the UI state after successful API call to resume", async () => {
		server.use(
			http.patch(buildApiUrl(`/work_pools/${pausedWorkPool.name}`), () => {
				return HttpResponse.json({});
			}),
		);

		render(<WorkPoolPauseResumeToggle workPool={pausedWorkPool} />, {
			wrapper: createWrapper(),
		});

		// Initially should show Paused
		expect(screen.getByText("Paused")).toBeInTheDocument();

		// Toggle to resume
		fireEvent.click(screen.getByRole("switch"));

		// After successful API call, should show Active
		await waitFor(() => {
			expect(screen.getByText("Active")).toBeInTheDocument();
		});
	});

	it("sets the correct aria-label based on the current state", () => {
		const { rerender } = render(
			<WorkPoolPauseResumeToggle workPool={activeWorkPool} />,
			{ wrapper: createWrapper() },
		);

		// When active, the aria-label should be to pause
		expect(screen.getByRole("switch")).toHaveAttribute(
			"aria-label",
			"Pause work pool",
		);

		// Rerender with paused work pool
		rerender(<WorkPoolPauseResumeToggle workPool={pausedWorkPool} />);

		// When paused, the aria-label should be to resume
		expect(screen.getByRole("switch")).toHaveAttribute(
			"aria-label",
			"Resume work pool",
		);
	});
});
