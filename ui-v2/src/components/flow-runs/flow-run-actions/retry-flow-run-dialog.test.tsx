import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createFakeFlowRun, createFakeState } from "@/mocks";
import { RetryFlowRunDialog } from "./retry-flow-run-dialog";

describe("RetryFlowRunDialog", () => {
	const mockOnOpenChange = vi.fn();
	const failedFlowRun = createFakeFlowRun({
		id: "test-flow-run-id",
		name: "test-flow-run",
		state_type: "FAILED",
		state_name: "Failed",
		state: createFakeState({
			type: "FAILED",
			name: "Failed",
		}),
		deployment_id: "test-deployment-id",
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
			<RetryFlowRunDialog
				flowRun={failedFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByRole("alertdialog")).toBeInTheDocument();
		expect(
			screen.getByRole("heading", { name: "Retry Flow Run" }),
		).toBeInTheDocument();
	});

	it("does not render dialog when closed", () => {
		render(
			<RetryFlowRunDialog
				flowRun={failedFlowRun}
				open={false}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
	});

	it("shows current state and target state badges", () => {
		render(
			<RetryFlowRunDialog
				flowRun={failedFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Current state:")).toBeInTheDocument();
		expect(screen.getByText("Will become:")).toBeInTheDocument();
		expect(screen.getByText("Failed")).toBeInTheDocument();
		expect(screen.getByText("AwaitingRetry")).toBeInTheDocument();
	});

	it("shows info text about persisted results", () => {
		render(
			<RetryFlowRunDialog
				flowRun={failedFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(
			screen.getByText(
				/Task runs with persisted results will use cached values/,
			),
		).toBeInTheDocument();
	});

	it("displays flow run name in confirmation message", () => {
		render(
			<RetryFlowRunDialog
				flowRun={failedFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("test-flow-run")).toBeInTheDocument();
	});

	it("calls setFlowRunState with SCHEDULED/AwaitingRetry on confirm", async () => {
		const user = userEvent.setup();
		let capturedRequest: {
			state: { type: string; name: string; message: string };
			force: boolean;
		} | null = null;

		server.use(
			http.post(
				buildApiUrl("/flow_runs/:id/set_state"),
				async ({ request }) => {
					capturedRequest = (await request.json()) as {
						state: { type: string; name: string; message: string };
						force: boolean;
					};
					return HttpResponse.json({ status: "ACCEPT" });
				},
			),
		);

		render(
			<RetryFlowRunDialog
				flowRun={failedFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		await user.click(screen.getByRole("button", { name: "Retry" }));

		await waitFor(() => {
			expect(capturedRequest).not.toBeNull();
			expect(capturedRequest?.state.type).toBe("SCHEDULED");
			expect(capturedRequest?.state.name).toBe("AwaitingRetry");
			expect(capturedRequest?.state.message).toBe("Retry from the UI");
			expect(capturedRequest?.force).toBe(true);
		});
	});

	it("closes dialog when cancel button is clicked", async () => {
		const user = userEvent.setup();

		render(
			<RetryFlowRunDialog
				flowRun={failedFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		await user.click(screen.getByRole("button", { name: "Cancel" }));

		expect(mockOnOpenChange).toHaveBeenCalledWith(false);
	});

	it("works with crashed flow runs", () => {
		const crashedFlowRun = createFakeFlowRun({
			id: "crashed-flow-run-id",
			name: "crashed-flow-run",
			state_type: "CRASHED",
			state_name: "Crashed",
			state: createFakeState({
				type: "CRASHED",
				name: "Crashed",
			}),
			deployment_id: "test-deployment-id",
		});

		render(
			<RetryFlowRunDialog
				flowRun={crashedFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Crashed")).toBeInTheDocument();
		expect(screen.getByText("AwaitingRetry")).toBeInTheDocument();
	});

	it("works with cancelled flow runs", () => {
		const cancelledFlowRun = createFakeFlowRun({
			id: "cancelled-flow-run-id",
			name: "cancelled-flow-run",
			state_type: "CANCELLED",
			state_name: "Cancelled",
			state: createFakeState({
				type: "CANCELLED",
				name: "Cancelled",
			}),
			deployment_id: "test-deployment-id",
		});

		render(
			<RetryFlowRunDialog
				flowRun={cancelledFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Cancelled")).toBeInTheDocument();
		expect(screen.getByText("AwaitingRetry")).toBeInTheDocument();
	});

	it("works with completed flow runs", () => {
		const completedFlowRun = createFakeFlowRun({
			id: "completed-flow-run-id",
			name: "completed-flow-run",
			state_type: "COMPLETED",
			state_name: "Completed",
			state: createFakeState({
				type: "COMPLETED",
				name: "Completed",
			}),
			deployment_id: "test-deployment-id",
		});

		render(
			<RetryFlowRunDialog
				flowRun={completedFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Completed")).toBeInTheDocument();
		expect(screen.getByText("AwaitingRetry")).toBeInTheDocument();
	});
});
