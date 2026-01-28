import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createFakeFlowRun, createFakeState } from "@/mocks";
import { PauseFlowRunDialog } from "./pause-flow-run-dialog";

describe("PauseFlowRunDialog", () => {
	const mockOnOpenChange = vi.fn();
	const runningFlowRun = createFakeFlowRun({
		id: "test-flow-run-id",
		name: "test-flow-run",
		state_type: "RUNNING",
		state_name: "Running",
		deployment_id: "test-deployment-id",
		state: createFakeState({
			type: "RUNNING",
			name: "Running",
		}),
	});

	beforeEach(() => {
		vi.clearAllMocks();

		server.use(
			http.post(buildApiUrl("/flow_runs/:id/set_state"), () => {
				return HttpResponse.json({ status: "ACCEPT" });
			}),
		);
	});

	it("renders dialog when open", () => {
		render(
			<PauseFlowRunDialog
				flowRun={runningFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByRole("dialog")).toBeInTheDocument();
		expect(
			screen.getByRole("heading", { name: "Pause Flow Run" }),
		).toBeInTheDocument();
	});

	it("does not render dialog when closed", () => {
		render(
			<PauseFlowRunDialog
				flowRun={runningFlowRun}
				open={false}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
	});

	it("shows default timeout of 300 seconds", () => {
		render(
			<PauseFlowRunDialog
				flowRun={runningFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		const input = screen.getByLabelText("Timeout (seconds)");
		expect(input).toHaveValue(300);
	});

	it("allows changing timeout value", () => {
		render(
			<PauseFlowRunDialog
				flowRun={runningFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		const input = screen.getByLabelText("Timeout (seconds)");
		// Use fireEvent.change to directly set the value
		fireEvent.change(input, { target: { value: "60" } });

		expect(input).toHaveValue(60);
	});

	it("shows current state and target state badges", () => {
		render(
			<PauseFlowRunDialog
				flowRun={runningFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Current state:")).toBeInTheDocument();
		expect(screen.getByText("Will become:")).toBeInTheDocument();
		expect(screen.getByText("Running")).toBeInTheDocument();
		expect(screen.getByText("Suspended")).toBeInTheDocument();
	});

	it("displays flow run name in description", () => {
		render(
			<PauseFlowRunDialog
				flowRun={runningFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("test-flow-run")).toBeInTheDocument();
	});

	it("calls setFlowRunState with PAUSED on confirm", async () => {
		const user = userEvent.setup();
		let capturedRequest: {
			state: { type: string; name: string; state_details?: object };
			force: boolean;
		} | null = null;

		server.use(
			http.post(
				buildApiUrl("/flow_runs/:id/set_state"),
				async ({ request }) => {
					capturedRequest = (await request.json()) as {
						state: { type: string; name: string; state_details?: object };
						force: boolean;
					};
					return HttpResponse.json({ status: "ACCEPT" });
				},
			),
		);

		render(
			<PauseFlowRunDialog
				flowRun={runningFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		await user.click(screen.getByRole("button", { name: "Pause Flow Run" }));

		await waitFor(() => {
			expect(capturedRequest).not.toBeNull();
			expect(capturedRequest?.state.type).toBe("PAUSED");
			expect(capturedRequest?.state.name).toBe("Suspended");
			expect(capturedRequest?.force).toBe(true);
			expect(capturedRequest?.state.state_details).toHaveProperty(
				"pause_timeout",
			);
			expect(capturedRequest?.state.state_details).toHaveProperty(
				"pause_reschedule",
				true,
			);
		});
	});

	it("closes dialog when cancel button is clicked", async () => {
		const user = userEvent.setup();

		render(
			<PauseFlowRunDialog
				flowRun={runningFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		await user.click(screen.getByRole("button", { name: "Cancel" }));

		expect(mockOnOpenChange).toHaveBeenCalledWith(false);
	});

	it("shows human-readable timeout preview", () => {
		render(
			<PauseFlowRunDialog
				flowRun={runningFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText(/Will pause for/)).toBeInTheDocument();
		expect(screen.getByText(/Minimum 5 seconds/)).toBeInTheDocument();
	});
});
