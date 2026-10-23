import { act, renderHook } from "@testing-library/react";
import { mockInMemoryLocalStorage } from "@tests/utils/browser";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	getPinnedDeploymentIds,
	PINNED_DEPLOYMENTS_STORAGE_KEY,
	usePinnedDeployments,
} from "./use-pinned-deployments";

describe("usePinnedDeployments", () => {
	let restoreLocalStorage: () => void;

	beforeEach(() => {
		restoreLocalStorage = mockInMemoryLocalStorage();
	});

	afterEach(() => {
		restoreLocalStorage();
	});

	it("starts with no pinned deployments", () => {
		const { result } = renderHook(() => usePinnedDeployments());

		expect(result.current.pinnedDeploymentIds).toEqual([]);
		expect(result.current.isPinned("deployment-1")).toBe(false);
	});

	it("pins and unpins a deployment", () => {
		const { result } = renderHook(() => usePinnedDeployments());

		act(() => {
			result.current.togglePin("deployment-1");
		});
		expect(result.current.pinnedDeploymentIds).toEqual(["deployment-1"]);
		expect(result.current.isPinned("deployment-1")).toBe(true);

		act(() => {
			result.current.togglePin("deployment-1");
		});
		expect(result.current.pinnedDeploymentIds).toEqual([]);
		expect(result.current.isPinned("deployment-1")).toBe(false);
	});

	it("persists pins to localStorage", () => {
		const { result } = renderHook(() => usePinnedDeployments());

		act(() => {
			result.current.togglePin("deployment-1");
		});
		act(() => {
			result.current.togglePin("deployment-2");
		});

		expect(localStorage.getItem(PINNED_DEPLOYMENTS_STORAGE_KEY)).toBe(
			JSON.stringify(["deployment-1", "deployment-2"]),
		);
		expect(getPinnedDeploymentIds()).toEqual(["deployment-1", "deployment-2"]);
	});

	it("restores pins saved by an earlier visit", () => {
		localStorage.setItem(
			PINNED_DEPLOYMENTS_STORAGE_KEY,
			JSON.stringify(["deployment-1"]),
		);

		const { result } = renderHook(() => usePinnedDeployments());

		expect(result.current.pinnedDeploymentIds).toEqual(["deployment-1"]);
	});

	it("shares pins between every component using the hook", () => {
		const first = renderHook(() => usePinnedDeployments());
		const second = renderHook(() => usePinnedDeployments());

		act(() => {
			first.result.current.togglePin("deployment-1");
		});

		expect(second.result.current.isPinned("deployment-1")).toBe(true);
	});

	it("picks up pins changed in another tab", () => {
		const { result } = renderHook(() => usePinnedDeployments());

		act(() => {
			localStorage.setItem(
				PINNED_DEPLOYMENTS_STORAGE_KEY,
				JSON.stringify(["deployment-1"]),
			);
			window.dispatchEvent(
				new StorageEvent("storage", { key: PINNED_DEPLOYMENTS_STORAGE_KEY }),
			);
		});

		expect(result.current.pinnedDeploymentIds).toEqual(["deployment-1"]);
	});

	it.each([
		["malformed JSON", "{not json"],
		["a value that is not a list of ids", JSON.stringify({ id: 1 })],
	])("ignores %s in localStorage", (_, storedValue) => {
		localStorage.setItem(PINNED_DEPLOYMENTS_STORAGE_KEY, storedValue);

		const { result } = renderHook(() => usePinnedDeployments());

		expect(result.current.pinnedDeploymentIds).toEqual([]);
	});

	it("reports a refused write and leaves pins unchanged", () => {
		const { result } = renderHook(() => usePinnedDeployments());
		act(() => {
			result.current.togglePin("deployment-1");
		});
		vi.spyOn(localStorage, "setItem").mockImplementation(() => {
			throw new DOMException("quota exceeded", "QuotaExceededError");
		});

		let saved: boolean | undefined;
		act(() => {
			saved = result.current.togglePin("deployment-2");
		});

		expect(saved).toBe(false);
		expect(result.current.pinnedDeploymentIds).toEqual(["deployment-1"]);
	});

	it("keeps the same list reference while pins are unchanged", () => {
		localStorage.setItem(
			PINNED_DEPLOYMENTS_STORAGE_KEY,
			JSON.stringify(["deployment-1"]),
		);
		const { result, rerender } = renderHook(() => usePinnedDeployments());
		const before = result.current.pinnedDeploymentIds;

		rerender();

		expect(result.current.pinnedDeploymentIds).toBe(before);
	});
});
