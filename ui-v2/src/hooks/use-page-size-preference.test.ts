/* eslint-disable @typescript-eslint/unbound-method */
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { usePageSizePreference } from "./use-page-size-preference";

describe("usePageSizePreference", () => {
	beforeEach(() => {
		vi.mocked(localStorage.getItem).mockReturnValue(null);
		vi.mocked(localStorage.setItem).mockClear();
	});

	it("returns URL page size when present", () => {
		const onInitialize = vi.fn();
		const { result } = renderHook(() =>
			usePageSizePreference(25, onInitialize),
		);
		expect(result.current).toBe(25);
		expect(onInitialize).not.toHaveBeenCalled();
	});

	it("calls onInitialize with stored value when URL page size is undefined", () => {
		vi.mocked(localStorage.getItem).mockReturnValueOnce(JSON.stringify(50));
		const onInitialize = vi.fn();
		renderHook(() => usePageSizePreference(undefined, onInitialize));
		expect(onInitialize).toHaveBeenCalledWith(50);
	});

	it("returns stored value when URL page size is undefined", () => {
		vi.mocked(localStorage.getItem).mockReturnValueOnce(JSON.stringify(50));
		const onInitialize = vi.fn();
		const { result } = renderHook(() =>
			usePageSizePreference(undefined, onInitialize),
		);
		expect(result.current).toBe(50);
	});

	it("returns default of 10 when nothing is stored and URL is undefined", () => {
		const onInitialize = vi.fn();
		const { result } = renderHook(() =>
			usePageSizePreference(undefined, onInitialize),
		);
		expect(result.current).toBe(10);
		expect(onInitialize).toHaveBeenCalledWith(10);
	});

	it("persists URL page size changes to localStorage", () => {
		const onInitialize = vi.fn();
		const { rerender } = renderHook(
			({ urlPageSize }: { urlPageSize: number | undefined }) =>
				usePageSizePreference(urlPageSize, onInitialize),
			{ initialProps: { urlPageSize: 10 } },
		);

		act(() => {
			rerender({ urlPageSize: 50 });
		});

		expect(localStorage.setItem).toHaveBeenCalledWith(
			"prefect-page-size",
			JSON.stringify(50),
		);
	});

	it("only calls onInitialize once even if re-rendered", () => {
		const onInitialize = vi.fn();
		const { rerender } = renderHook(() =>
			usePageSizePreference(undefined, onInitialize),
		);
		rerender();
		rerender();
		expect(onInitialize).toHaveBeenCalledTimes(1);
	});
});
