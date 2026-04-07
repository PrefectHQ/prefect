import { QueryClient } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { createFakeVariable } from "@/mocks/create-fake-variable";
import { useDeleteVariableConfirmationDialog } from "./use-delete-variable-confirmation-dialog";

describe("useDeleteVariableConfirmationDialog", () => {
	it("initializes with dialog closed", () => {
		const queryClient = new QueryClient();
		const { result } = renderHook(() => useDeleteVariableConfirmationDialog(), {
			wrapper: createWrapper({ queryClient }),
		});
		const [dialogState] = result.current;

		expect(dialogState.isOpen).toBe(false);
	});

	it("opens dialog with variable name in description when delete is triggered", () => {
		const queryClient = new QueryClient();
		const { result } = renderHook(() => useDeleteVariableConfirmationDialog(), {
			wrapper: createWrapper({ queryClient }),
		});

		const variable = createFakeVariable({ name: "my-test-variable" });

		act(() => {
			const [, handleConfirmDelete] = result.current;
			handleConfirmDelete(variable);
		});

		const [dialogState] = result.current;
		expect(dialogState.isOpen).toBe(true);
		expect(dialogState.title).toBe("Delete Variable");
		expect(dialogState.description).toContain("my-test-variable");
	});

	it("calls deleteVariable API when confirmed", () => {
		const mockVariable = createFakeVariable();

		server.use(
			http.delete(buildApiUrl("/variables/:id"), () => {
				return HttpResponse.json(null, { status: 204 });
			}),
		);

		const queryClient = new QueryClient();
		const { result } = renderHook(() => useDeleteVariableConfirmationDialog(), {
			wrapper: createWrapper({ queryClient }),
		});

		act(() => {
			const [, handleConfirmDelete] = result.current;
			handleConfirmDelete(mockVariable);
		});

		act(() => {
			const [dialogState] = result.current;
			dialogState.onConfirm();
		});

		const [dialogState] = result.current;
		expect(dialogState.isOpen).toBe(false);
	});

	it("closes dialog when onClose is called", () => {
		const queryClient = new QueryClient();
		const { result } = renderHook(() => useDeleteVariableConfirmationDialog(), {
			wrapper: createWrapper({ queryClient }),
		});

		const variable = createFakeVariable();

		act(() => {
			const [, handleConfirmDelete] = result.current;
			handleConfirmDelete(variable);
		});

		expect(result.current[0].isOpen).toBe(true);

		act(() => {
			const [dialogState] = result.current;
			dialogState.onClose();
		});

		expect(result.current[0].isOpen).toBe(false);
	});
});
