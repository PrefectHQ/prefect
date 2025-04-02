import type { FlowRun } from "@/api/flow-runs";
import { Toaster } from "@/components/ui/sonner";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { expect, test, vi } from "vitest";

import { FlowRunStateDialog } from "./flow-run-state-dialog";

type SetFlowRunStateParams = {
	id: string;
	state: string;
	message?: string;
	name?: string;
	force?: boolean;
};

type MutationCallbacks = {
	onSuccess?: () => void;
	onError?: (error: Error) => void;
};

vi.mock("@/api/flow-runs", async () => {
	const actual = await vi.importActual("@/api/flow-runs");
	return {
		...actual,
		useSetFlowRunState: () => ({
			setFlowRunState: vi.fn(
				(_params: SetFlowRunStateParams, callbacks: MutationCallbacks) => {
					callbacks?.onSuccess?.();
				},
			),
		}),
	};
});

// Create a mock flow run with completed state
const mockFlowRun = {
	id: "test-flow-run-id",
	name: "Test Flow Run",
	state: {
		type: "COMPLETED",
		name: "Completed",
		timestamp: "2023-10-15T10:30:00Z",
	},
} as FlowRun;

test("FlowRunStateDialog renders correctly", () => {
	render(
		<FlowRunStateDialog
			flowRun={mockFlowRun}
			open={true}
			onOpenChange={vi.fn()}
		/>,
		{ wrapper: createWrapper() },
	);

	// Check dialog title
	expect(
		screen.getByRole("heading", { name: /change flow run state/i }),
	).toBeInTheDocument();

	// Check current state is displayed
	expect(screen.getByText(/current flow run state/i)).toBeInTheDocument();
	// Use getAllByText for elements that might appear multiple times
	expect(screen.getAllByText(/completed/i)[0]).toBeInTheDocument();

	// Check form fields - find by text instead of label association which may be implementation-specific
	expect(screen.getByText(/desired flow run state/i)).toBeInTheDocument();
	expect(screen.getByText(/reason \(optional\)/i)).toBeInTheDocument();

	// Check buttons - using getAllByRole because there are multiple close buttons
	expect(screen.getAllByRole("button", { name: /close/i })).toHaveLength(2);
	expect(screen.getByRole("button", { name: /change/i })).toBeInTheDocument();
});

test("Component handles the current state appropriately", () => {
	render(
		<FlowRunStateDialog
			flowRun={mockFlowRun}
			open={true}
			onOpenChange={vi.fn()}
		/>,
		{ wrapper: createWrapper() },
	);

	// Verify the current state is displayed
	const currentStateSection = screen
		.getByText(/current flow run state/i)
		.closest("div");
	expect(currentStateSection).toBeInTheDocument();
	expect(currentStateSection).toHaveTextContent(/completed/i);

	// Verify the state selector is available
	const stateSelector = screen.getByRole("combobox", { name: /select state/i });
	expect(stateSelector).toBeInTheDocument();

	// Verify it defaults to a different state (not the current one)
	expect(stateSelector.textContent).not.toMatch(/completed/i);
});

test("FlowRunStateDialog can submit state change", async () => {
	const user = userEvent.setup();
	const onOpenChangeMock = vi.fn();

	render(
		<>
			<Toaster />
			<FlowRunStateDialog
				flowRun={mockFlowRun}
				open={true}
				onOpenChange={onOpenChangeMock}
			/>
		</>,
		{ wrapper: createWrapper() },
	);

	await user.click(screen.getByRole("button", { name: /change/i }));

	await waitFor(() => {
		expect(onOpenChangeMock).toHaveBeenCalledWith(false);
	});
});

test("FlowRunStateDialog defaults to a state different than the current one", () => {
	render(
		<FlowRunStateDialog
			flowRun={mockFlowRun}
			open={true}
			onOpenChange={vi.fn()}
		/>,
		{ wrapper: createWrapper() },
	);

	// The current state is COMPLETED, so the form should default to a different state
	const selectValue = screen.getByRole("combobox", { name: /select state/i });
	// Should not contain "Completed" as the selected value
	expect(selectValue.textContent).not.toMatch(/completed/i);
});
