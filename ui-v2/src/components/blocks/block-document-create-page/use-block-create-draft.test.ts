import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useBlockCreateDraft } from "./use-block-create-draft";

const mockGetItem = vi.spyOn(localStorage, "getItem");
const mockSetItem = vi.spyOn(localStorage, "setItem");

describe("useBlockCreateDraft", () => {
	afterEach(() => {
		mockGetItem.mockReset();
		mockSetItem.mockReset();
	});

	it("returns empty draft when no saved data exists", () => {
		mockGetItem.mockReturnValue(null);

		const { result } = renderHook(() => useBlockCreateDraft("my-block-type"));

		expect(result.current.draft).toEqual({
			blockName: "",
			values: {},
		});
		expect(mockGetItem).toHaveBeenCalledWith(
			"prefect-ui-v2-block-create-draft-my-block-type",
		);
	});

	it("persists block name updates to localStorage", () => {
		mockGetItem.mockReturnValue(null);

		const { result } = renderHook(() => useBlockCreateDraft("my-block-type"));

		act(() => {
			result.current.updateDraft({ blockName: "my-block" });
		});

		expect(result.current.draft.blockName).toBe("my-block");
		expect(mockSetItem).toHaveBeenCalledWith(
			"prefect-ui-v2-block-create-draft-my-block-type",
			expect.stringContaining('"blockName":"my-block"'),
		);
	});

	it("persists schema form values to localStorage", () => {
		mockGetItem.mockReturnValue(null);

		const { result } = renderHook(() => useBlockCreateDraft("my-block-type"));

		const testValues = { aws_access_key_id: "AKIA...", region: "us-east-1" };
		act(() => {
			result.current.updateDraft({ values: testValues });
		});

		expect(result.current.draft.values).toEqual(testValues);
		expect(mockSetItem).toHaveBeenCalledWith(
			"prefect-ui-v2-block-create-draft-my-block-type",
			expect.stringContaining('"aws_access_key_id":"AKIA..."'),
		);
	});

	it("restores saved draft on mount", () => {
		const draft = {
			blockName: "restored-block",
			values: { key: "restored-value" },
		};
		mockGetItem.mockReturnValue(JSON.stringify(draft));

		const { result } = renderHook(() => useBlockCreateDraft("my-block-type"));

		expect(result.current.draft.blockName).toBe("restored-block");
		expect(result.current.draft.values).toEqual({ key: "restored-value" });
	});

	it("clears draft state", () => {
		const draft = {
			blockName: "to-clear",
			values: { key: "value" },
		};
		mockGetItem.mockReturnValue(JSON.stringify(draft));

		const { result } = renderHook(() => useBlockCreateDraft("my-block-type"));

		expect(result.current.draft.blockName).toBe("to-clear");

		act(() => {
			result.current.clearDraft();
		});

		expect(result.current.draft).toEqual({ blockName: "", values: {} });
	});

	it("uses separate keys per block type slug", () => {
		mockGetItem.mockReturnValue(null);

		renderHook(() => useBlockCreateDraft("type-a"));
		renderHook(() => useBlockCreateDraft("type-b"));

		expect(mockGetItem).toHaveBeenCalledWith(
			"prefect-ui-v2-block-create-draft-type-a",
		);
		expect(mockGetItem).toHaveBeenCalledWith(
			"prefect-ui-v2-block-create-draft-type-b",
		);
	});
});
