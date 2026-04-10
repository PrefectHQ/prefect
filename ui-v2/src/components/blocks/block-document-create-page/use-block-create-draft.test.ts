import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useBlockCreateDraft } from "./use-block-create-draft";

describe("useBlockCreateDraft", () => {
	afterEach(() => {
		vi.mocked(localStorage.getItem).mockReset();
		vi.mocked(localStorage.setItem).mockReset();
		vi.mocked(localStorage.removeItem).mockReset();
	});

	it("returns empty draft when no saved data exists", () => {
		vi.mocked(localStorage.getItem).mockReturnValue(null);

		const { result } = renderHook(() => useBlockCreateDraft("my-block-type"));

		expect(result.current.draft).toEqual({
			blockName: "",
			values: {},
		});
		expect(localStorage.getItem).toHaveBeenCalledWith(
			"prefect-ui-v2-block-create-draft-my-block-type",
		);
	});

	it("persists block name updates to localStorage", () => {
		vi.mocked(localStorage.getItem).mockReturnValue(null);

		const { result } = renderHook(() => useBlockCreateDraft("my-block-type"));

		act(() => {
			result.current.updateDraft({ blockName: "my-block" });
		});

		expect(result.current.draft.blockName).toBe("my-block");
		expect(localStorage.setItem).toHaveBeenCalledWith(
			"prefect-ui-v2-block-create-draft-my-block-type",
			expect.stringContaining('"blockName":"my-block"'),
		);
	});

	it("persists schema form values to localStorage", () => {
		vi.mocked(localStorage.getItem).mockReturnValue(null);

		const { result } = renderHook(() => useBlockCreateDraft("my-block-type"));

		const testValues = { aws_access_key_id: "AKIA...", region: "us-east-1" };
		act(() => {
			result.current.updateDraft({ values: testValues });
		});

		expect(result.current.draft.values).toEqual(testValues);
		expect(localStorage.setItem).toHaveBeenCalledWith(
			"prefect-ui-v2-block-create-draft-my-block-type",
			expect.stringContaining('"aws_access_key_id":"AKIA..."'),
		);
	});

	it("restores saved draft on mount", () => {
		const draft = {
			blockName: "restored-block",
			values: { key: "restored-value" },
		};
		vi.mocked(localStorage.getItem).mockReturnValue(JSON.stringify(draft));

		const { result } = renderHook(() => useBlockCreateDraft("my-block-type"));

		expect(result.current.draft.blockName).toBe("restored-block");
		expect(result.current.draft.values).toEqual({ key: "restored-value" });
	});

	it("clears draft from state and localStorage", () => {
		const draft = {
			blockName: "to-clear",
			values: { key: "value" },
		};
		vi.mocked(localStorage.getItem).mockReturnValue(JSON.stringify(draft));

		const { result } = renderHook(() => useBlockCreateDraft("my-block-type"));

		expect(result.current.draft.blockName).toBe("to-clear");

		act(() => {
			result.current.clearDraft();
		});

		expect(result.current.draft).toEqual({ blockName: "", values: {} });
		expect(localStorage.removeItem).toHaveBeenCalledWith(
			"prefect-ui-v2-block-create-draft-my-block-type",
		);
	});

	it("uses separate keys per block type slug", () => {
		vi.mocked(localStorage.getItem).mockReturnValue(null);

		renderHook(() => useBlockCreateDraft("type-a"));
		renderHook(() => useBlockCreateDraft("type-b"));

		expect(localStorage.getItem).toHaveBeenCalledWith(
			"prefect-ui-v2-block-create-draft-type-a",
		);
		expect(localStorage.getItem).toHaveBeenCalledWith(
			"prefect-ui-v2-block-create-draft-type-b",
		);
	});
});
