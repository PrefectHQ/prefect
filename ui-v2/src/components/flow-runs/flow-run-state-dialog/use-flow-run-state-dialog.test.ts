import type { FlowRun } from "@/api/flow-runs";
import { act, renderHook } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it } from "vitest";
import { useFlowRunStateDialog } from "./use-flow-run-state-dialog";

describe("useFlowRunStateDialog", () => {
	// Create a mock flow run
	const mockFlowRun = {
		id: "test-flow-run-id",
		name: "Test Flow Run",
		state: {
			type: "COMPLETED",
			name: "Completed",
			timestamp: "2023-10-15T10:30:00Z",
		},
	} as FlowRun;

	it("initializes with default closed state", () => {
		const { result } = renderHook(() => useFlowRunStateDialog(), {
			wrapper: createWrapper(),
		});
		const [dialogState] = result.current;

		expect(dialogState.open).toBe(false);
		expect(dialogState.flowRun).toEqual({} as FlowRun);
	});

	it("opens dialog with flow run", () => {
		const { result } = renderHook(() => useFlowRunStateDialog(), {
			wrapper: createWrapper(),
		});

		act(() => {
			const [, openDialog] = result.current;
			openDialog(mockFlowRun);
		});

		const [dialogState] = result.current;
		expect(dialogState.open).toBe(true);
		expect(dialogState.flowRun).toEqual(mockFlowRun);
	});

	it("closes dialog when onOpenChange is called with false", () => {
		const { result } = renderHook(() => useFlowRunStateDialog(), {
			wrapper: createWrapper(),
		});

		// First "open" the dialog
		act(() => {
			const [, openDialog] = result.current;
			openDialog(mockFlowRun);
		});

		// Then close it
		act(() => {
			const [dialogState] = result.current;
			dialogState.onOpenChange(false);
		});

		const [finalState] = result.current;
		expect(finalState.open).toBe(false);
	});
});
