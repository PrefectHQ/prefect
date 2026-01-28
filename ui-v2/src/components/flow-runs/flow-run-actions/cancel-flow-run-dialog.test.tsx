import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createFakeFlowRun, createFakeState } from "@/mocks";
import { CancelFlowRunDialog } from "./cancel-flow-run-dialog";

describe("CancelFlowRunDialog", () => {
	const mockOnOpenChange = vi.fn();
	const runningFlowRun = createFakeFlowRun({
		id: "test-flow-run-id",
		name: "test-flow-run",
		state_type: "RUNNING",
		state_name: "Running",
		state: createFakeState({
			type: "RUNNING",
			name: "Running",
		}),
	});

	beforeEach(() => {
		vi.clearAllMocks();

		server.use(
			http.post(buildApiUrl("/flow_runs/filter"), () => {
				return HttpResponse.json([]);
			}),
			http.post(buildApiUrl("/flow_runs/:id/set_state"), () => {
				return HttpResponse.json({ status: "ACCEPT" });
			}),
		);
	});

	it("renders dialog when open", () => {
		render(
			<CancelFlowRunDialog
				flowRun={runningFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByRole("alertdialog")).toBeInTheDocument();
		expect(
			screen.getByRole("heading", { name: "Cancel Flow Run" }),
		).toBeInTheDocument();
	});

	it("does not render dialog when closed", () => {
		render(
			<CancelFlowRunDialog
				flowRun={runningFlowRun}
				open={false}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
	});

	it("shows current state and target state badges", () => {
		render(
			<CancelFlowRunDialog
				flowRun={runningFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Current state:")).toBeInTheDocument();
		expect(screen.getByText("Will become:")).toBeInTheDocument();
		expect(screen.getByText("Running")).toBeInTheDocument();
		expect(screen.getByText("Cancelling")).toBeInTheDocument();
	});

	it("displays flow run name in confirmation message", () => {
		render(
			<CancelFlowRunDialog
				flowRun={runningFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("test-flow-run")).toBeInTheDocument();
	});

	it("calls setFlowRunState with CANCELLING on confirm", async () => {
		const user = userEvent.setup();
		let capturedRequest: { state: { type: string; name: string } } | null =
			null;

		server.use(
			http.post(
				buildApiUrl("/flow_runs/:id/set_state"),
				async ({ request }) => {
					capturedRequest = (await request.json()) as {
						state: { type: string; name: string };
					};
					return HttpResponse.json({ status: "ACCEPT" });
				},
			),
		);

		render(
			<CancelFlowRunDialog
				flowRun={runningFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		await user.click(screen.getByRole("button", { name: "Cancel Flow Run" }));

		await waitFor(() => {
			expect(capturedRequest).not.toBeNull();
			expect(capturedRequest?.state.type).toBe("CANCELLING");
			expect(capturedRequest?.state.name).toBe("Cancelling");
		});
	});

	it("closes dialog when cancel button is clicked", async () => {
		const user = userEvent.setup();

		render(
			<CancelFlowRunDialog
				flowRun={runningFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		await user.click(screen.getByRole("button", { name: "Cancel" }));

		expect(mockOnOpenChange).toHaveBeenCalledWith(false);
	});

	it("shows sub-flow checkbox when sub-flows exist", async () => {
		const subFlowRun = createFakeFlowRun({
			id: "sub-flow-run-id",
			name: "sub-flow-run",
			state_type: "RUNNING",
			state_name: "Running",
		});

		server.use(
			http.post(buildApiUrl("/flow_runs/filter"), () => {
				return HttpResponse.json([subFlowRun]);
			}),
		);

		render(
			<CancelFlowRunDialog
				flowRun={runningFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(
				screen.getByText(/Also cancel 1 sub-flow run$/),
			).toBeInTheDocument();
		});

		expect(screen.getByRole("checkbox")).toBeInTheDocument();
	});

	it("does not show sub-flow checkbox when no sub-flows exist", async () => {
		server.use(
			http.post(buildApiUrl("/flow_runs/filter"), () => {
				return HttpResponse.json([]);
			}),
		);

		render(
			<CancelFlowRunDialog
				flowRun={runningFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(
				screen.getByRole("heading", { name: "Cancel Flow Run" }),
			).toBeInTheDocument();
		});

		expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
	});

	it("shows plural text for multiple sub-flows", async () => {
		const subFlowRuns = [
			createFakeFlowRun({
				id: "sub-flow-run-1",
				name: "sub-flow-run-1",
				state_type: "RUNNING",
				state_name: "Running",
			}),
			createFakeFlowRun({
				id: "sub-flow-run-2",
				name: "sub-flow-run-2",
				state_type: "SCHEDULED",
				state_name: "Scheduled",
			}),
		];

		server.use(
			http.post(buildApiUrl("/flow_runs/filter"), () => {
				return HttpResponse.json(subFlowRuns);
			}),
		);

		render(
			<CancelFlowRunDialog
				flowRun={runningFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(
				screen.getByText(/Also cancel 2 sub-flow runs$/),
			).toBeInTheDocument();
		});
	});

	it("works with scheduled flow runs", () => {
		const scheduledFlowRun = createFakeFlowRun({
			id: "scheduled-flow-run-id",
			name: "scheduled-flow-run",
			state_type: "SCHEDULED",
			state_name: "Scheduled",
			state: createFakeState({
				type: "SCHEDULED",
				name: "Scheduled",
			}),
		});

		render(
			<CancelFlowRunDialog
				flowRun={scheduledFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Scheduled")).toBeInTheDocument();
		expect(screen.getByText("Cancelling")).toBeInTheDocument();
	});

	it("works with paused flow runs", () => {
		const pausedFlowRun = createFakeFlowRun({
			id: "paused-flow-run-id",
			name: "paused-flow-run",
			state_type: "PAUSED",
			state_name: "Paused",
			state: createFakeState({
				type: "PAUSED",
				name: "Paused",
			}),
		});

		render(
			<CancelFlowRunDialog
				flowRun={pausedFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Paused")).toBeInTheDocument();
		expect(screen.getByText("Cancelling")).toBeInTheDocument();
	});
});
