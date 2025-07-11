import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { createFakeWorkPool } from "@/mocks/create-fake-work-pool";
import { WorkPoolPauseResumeToggle } from "./work-pool-pause-resume-toggle";

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
		render(
			<>
				<Toaster />
				<WorkPoolPauseResumeToggle workPool={activeWorkPool} />
			</>,
			{
				wrapper: createWrapper(),
			},
		);

		expect(screen.getByText("Active")).toBeInTheDocument();
		expect(screen.getByRole("switch")).toBeChecked();
	});

	it("renders the paused state correctly", () => {
		render(
			<>
				<Toaster />
				<WorkPoolPauseResumeToggle workPool={pausedWorkPool} />
			</>,
			{
				wrapper: createWrapper(),
			},
		);

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

		render(
			<>
				<Toaster />
				<WorkPoolPauseResumeToggle workPool={activeWorkPool} />
			</>,
			{
				wrapper: createWrapper(),
			},
		);

		const user = userEvent.setup();

		const toggle = screen.getByRole("switch", { name: /pause work pool/i });

		await user.click(toggle);

		expect(toggle).toBeDisabled();

		await waitFor(() => {
			expect(
				screen.getByText(`${activeWorkPool.name} paused`),
			).toBeInTheDocument();
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

		render(
			<>
				<Toaster />
				<WorkPoolPauseResumeToggle workPool={activeWorkPool} />
			</>,
			{
				wrapper: createWrapper(),
			},
		);

		const user = userEvent.setup();

		await user.click(screen.getByRole("switch"));

		await waitFor(() => {
			expect(
				screen.getByText(`Failed to pause ${activeWorkPool.name}`),
			).toBeInTheDocument();
		});
	});

	it("updates the UI state after successful API call to pause", async () => {
		server.use(
			http.patch(buildApiUrl(`/work_pools/${activeWorkPool.name}`), () => {
				return HttpResponse.json({});
			}),
		);

		render(
			<>
				<Toaster />
				<WorkPoolPauseResumeToggle workPool={activeWorkPool} />
			</>,
			{
				wrapper: createWrapper(),
			},
		);

		const user = userEvent.setup();

		// Initially should show Active
		expect(screen.getByText("Active")).toBeInTheDocument();

		// Toggle to pause
		await user.click(screen.getByRole("switch"));

		// After successful API call, should show Paused and success toast
		await waitFor(() => {
			expect(screen.getByText("Paused")).toBeInTheDocument();
			expect(
				screen.getByText(`${activeWorkPool.name} paused`),
			).toBeInTheDocument();
		});
	});

	it("updates the UI state after successful API call to resume", async () => {
		server.use(
			http.patch(buildApiUrl(`/work_pools/${pausedWorkPool.name}`), () => {
				return HttpResponse.json({});
			}),
		);

		render(
			<>
				<Toaster />
				<WorkPoolPauseResumeToggle workPool={pausedWorkPool} />
			</>,
			{
				wrapper: createWrapper(),
			},
		);

		// Initially should show Paused
		expect(screen.getByText("Paused")).toBeInTheDocument();

		// Toggle to resume
		const user = userEvent.setup();
		await user.click(screen.getByRole("switch"));

		// After successful API call, should show Active and success toast
		await waitFor(() => {
			expect(screen.getByText("Active")).toBeInTheDocument();
			expect(
				screen.getByText(`${pausedWorkPool.name} resumed`),
			).toBeInTheDocument();
		});
	});

	it("shows error toast when resume operation fails", async () => {
		server.use(
			http.patch(buildApiUrl(`/work_pools/${pausedWorkPool.name}`), () => {
				return HttpResponse.json(
					{ detail: "Failed to resume" },
					{ status: 500 },
				);
			}),
		);

		render(
			<>
				<Toaster />
				<WorkPoolPauseResumeToggle workPool={pausedWorkPool} />
			</>,
			{
				wrapper: createWrapper(),
			},
		);

		const user = userEvent.setup();

		await user.click(screen.getByRole("switch"));

		await waitFor(() => {
			expect(
				screen.getByText(`Failed to resume ${pausedWorkPool.name}`),
			).toBeInTheDocument();
		});
	});

	it("sets the correct aria-label when the work pool is active", () => {
		expect(activeWorkPool.is_paused).toBe(false);

		render(
			<>
				<Toaster />
				<WorkPoolPauseResumeToggle workPool={activeWorkPool} />
			</>,
			{ wrapper: createWrapper() },
		);

		// When active, the aria-label should be to pause
		expect(screen.getByRole("switch")).toHaveAttribute(
			"aria-label",
			"Pause work pool",
		);
	});

	it("sets the correct aria-label when the work pool is paused", () => {
		expect(pausedWorkPool.is_paused).toBe(true);

		// Rerender with paused work pool
		render(
			<>
				<Toaster />
				<WorkPoolPauseResumeToggle workPool={pausedWorkPool} />
			</>,
			{ wrapper: createWrapper() },
		);

		// When paused, the aria-label should be to resume
		expect(screen.getByRole("switch")).toHaveAttribute(
			"aria-label",
			"Resume work pool",
		);
	});
});
