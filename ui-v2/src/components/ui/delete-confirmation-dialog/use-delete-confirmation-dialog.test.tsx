import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useDeleteConfirmationDialog } from "./use-delete-confirmation-dialog";

describe("useDeleteConfirmationDialog", () => {
	it("initializes with default closed state", () => {
		const { result } = renderHook(() => useDeleteConfirmationDialog());
		const [dialogState] = result.current;

		expect(dialogState.isOpen).toBe(false);
		expect(dialogState.title).toBe("");
		expect(dialogState.description).toBe("");
	});

	it("opens dialog with provided config", () => {
		const { result } = renderHook(() => useDeleteConfirmationDialog());
		const onConfirm = vi.fn();

		act(() => {
			const [, confirmDelete] = result.current;
			confirmDelete({
				title: "Custom Title",
				description: "Custom Description",
				onConfirm,
			});
		});

		const [dialogState] = result.current;
		expect(dialogState.isOpen).toBe(true);
		expect(dialogState.title).toBe("Custom Title");
		expect(dialogState.description).toBe("Custom Description");
	});

	it("uses default title and description when not provided", () => {
		const { result } = renderHook(() => useDeleteConfirmationDialog());
		const onConfirm = vi.fn();

		act(() => {
			const [, confirmDelete] = result.current;
			confirmDelete({ onConfirm });
		});

		const [dialogState] = result.current;
		expect(dialogState.title).toBe("Confirm Deletion");
		expect(dialogState.description).toBe(
			"Are you sure you want to delete this item? This action cannot be undone.",
		);
	});

	it("closes dialog when onClose is called", () => {
		const { result } = renderHook(() => useDeleteConfirmationDialog());

		// First "open" the dialog
		act(() => {
			const [, confirmDelete] = result.current;
			confirmDelete({ onConfirm: vi.fn() });
		});

		// Then close it
		act(() => {
			const [dialogState] = result.current;
			dialogState.onClose();
		});

		const [finalState] = result.current;
		expect(finalState.isOpen).toBe(false);
	});

	it("call the provided onConfirm callback", () => {
		const { result } = renderHook(() => useDeleteConfirmationDialog());
		const onConfirm = vi.fn();

		// "Open" the dialog
		act(() => {
			const [, confirmDelete] = result.current;
			confirmDelete({ onConfirm });
		});

		// Trigger onConfirm
		act(() => {
			const [dialogState] = result.current;
			dialogState.onConfirm();
		});

		expect(onConfirm).toHaveBeenCalledTimes(1);
	});
});
