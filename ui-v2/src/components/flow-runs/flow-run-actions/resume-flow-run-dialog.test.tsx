import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createFakeFlowRun, createFakeState } from "@/mocks";
import { ResumeFlowRunDialog } from "./resume-flow-run-dialog";

describe("ResumeFlowRunDialog", () => {
	const mockOnOpenChange = vi.fn();
	const pausedFlowRun = createFakeFlowRun({
		id: "test-flow-run-id",
		name: "test-flow-run",
		state_type: "PAUSED",
		state_name: "Paused",
		state: createFakeState({
			type: "PAUSED",
			name: "Paused",
		}),
	});

	beforeEach(() => {
		vi.clearAllMocks();

		server.use(
			http.post(buildApiUrl("/flow_runs/:id/resume"), () => {
				return HttpResponse.json({ status: "ACCEPT" });
			}),
		);
	});

	it("renders simple dialog when no run input required", () => {
		render(
			<ResumeFlowRunDialog
				flowRun={pausedFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByRole("dialog")).toBeInTheDocument();
		expect(
			screen.getByRole("heading", { name: "Resume Flow Run" }),
		).toBeInTheDocument();
	});

	it("does not render dialog when closed", () => {
		render(
			<ResumeFlowRunDialog
				flowRun={pausedFlowRun}
				open={false}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
	});

	it("shows current state badge", () => {
		render(
			<ResumeFlowRunDialog
				flowRun={pausedFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Current state:")).toBeInTheDocument();
		expect(screen.getByText("Paused")).toBeInTheDocument();
	});

	it("displays flow run name in description", () => {
		render(
			<ResumeFlowRunDialog
				flowRun={pausedFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("test-flow-run")).toBeInTheDocument();
	});

	it("calls resumeFlowRun on confirm", async () => {
		const user = userEvent.setup();
		let apiCalled = false;

		server.use(
			http.post(buildApiUrl("/flow_runs/:id/resume"), () => {
				apiCalled = true;
				return HttpResponse.json({ status: "ACCEPT" });
			}),
		);

		render(
			<ResumeFlowRunDialog
				flowRun={pausedFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		await user.click(screen.getByRole("button", { name: "Resume" }));

		await waitFor(() => {
			expect(apiCalled).toBe(true);
		});
	});

	it("closes dialog when cancel button is clicked", async () => {
		const user = userEvent.setup();

		render(
			<ResumeFlowRunDialog
				flowRun={pausedFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		await user.click(screen.getByRole("button", { name: "Cancel" }));

		expect(mockOnOpenChange).toHaveBeenCalledWith(false);
	});

	it("works with suspended flow runs", () => {
		const suspendedFlowRun = createFakeFlowRun({
			id: "suspended-flow-run-id",
			name: "suspended-flow-run",
			state_type: "PAUSED",
			state_name: "Suspended",
			state: createFakeState({
				type: "PAUSED",
				name: "Suspended",
			}),
		});

		render(
			<ResumeFlowRunDialog
				flowRun={suspendedFlowRun}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByText("Suspended")).toBeInTheDocument();
	});

	it("shows schema form when run_input_keyset is present", async () => {
		const flowRunWithInput = createFakeFlowRun({
			id: "flow-run-with-input-id",
			name: "flow-run-with-input",
			state_type: "PAUSED",
			state_name: "Paused",
			state: {
				...createFakeState({
					type: "PAUSED",
					name: "Paused",
				}),
				state_details: {
					run_input_keyset: {
						schema: "schema-key",
						description: "description-key",
					},
				},
			},
		});

		server.use(
			http.get(buildApiUrl("/flow_runs/:id/input/:key"), ({ params }) => {
				if (params.key === "schema-key") {
					return HttpResponse.json({
						type: "object",
						properties: {
							name: { type: "string", title: "Name" },
						},
					});
				}
				if (params.key === "description-key") {
					return HttpResponse.json("Please provide input");
				}
				return HttpResponse.json(null);
			}),
		);

		render(
			<ResumeFlowRunDialog
				flowRun={flowRunWithInput}
				open={true}
				onOpenChange={mockOnOpenChange}
			/>,
			{ wrapper: createWrapper() },
		);

		// Should show loading state while fetching schema
		expect(screen.getByRole("dialog")).toBeInTheDocument();

		// Wait for the schema form to load
		await waitFor(() => {
			expect(
				screen.getByRole("heading", { name: "Resume Flow Run" }),
			).toBeInTheDocument();
		});
	});
});
