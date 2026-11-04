import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useStickyHoverTarget } from "./use-sticky-hover-target";

type Target = { id: string; x: number };

const getKey = (target: Target) => target.id;

type Props = { candidate: Target | undefined; enabled?: boolean };

const renderSticky = (initial: Target | undefined) =>
	renderHook<ReturnType<typeof useStickyHoverTarget<Target>>, Props>(
		({ candidate, enabled = true }) =>
			useStickyHoverTarget(candidate, getKey, { switchDelay: 150, enabled }),
		{ initialProps: { candidate: initial } },
	);

describe("useStickyHoverTarget", () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it("shows the first candidate immediately", () => {
		const { result, rerender } = renderSticky(undefined);
		expect(result.current.target).toBeUndefined();

		rerender({ candidate: { id: "a", x: 1 } });
		expect(result.current.target).toEqual({ id: "a", x: 1 });
	});

	it("keeps the current target until the switch delay elapses", () => {
		const { result, rerender } = renderSticky({ id: "a", x: 1 });

		rerender({ candidate: { id: "b", x: 2 } });
		expect(result.current.target).toEqual({ id: "a", x: 1 });

		act(() => {
			vi.advanceTimersByTime(149);
		});
		expect(result.current.target).toEqual({ id: "a", x: 1 });

		act(() => {
			vi.advanceTimersByTime(1);
		});
		expect(result.current.target).toEqual({ id: "b", x: 2 });
	});

	it("does not switch when the candidate returns before the delay elapses", () => {
		const { result, rerender } = renderSticky({ id: "a", x: 1 });

		rerender({ candidate: { id: "b", x: 2 } });
		act(() => {
			vi.advanceTimersByTime(100);
		});
		rerender({ candidate: { id: "a", x: 1 } });
		act(() => {
			vi.advanceTimersByTime(200);
		});

		expect(result.current.target).toEqual({ id: "a", x: 1 });
	});

	it("does not restart the delay when the same candidate re-renders", () => {
		const { result, rerender } = renderSticky({ id: "a", x: 1 });

		rerender({ candidate: { id: "b", x: 2 } });
		act(() => {
			vi.advanceTimersByTime(100);
		});
		rerender({ candidate: { id: "b", x: 3 } });
		act(() => {
			vi.advanceTimersByTime(50);
		});

		expect(result.current.target).toEqual({ id: "b", x: 3 });
	});

	it("clears the target after the delay when there is no candidate", () => {
		const { result, rerender } = renderSticky({ id: "a", x: 1 });

		rerender({ candidate: undefined });
		expect(result.current.target).toEqual({ id: "a", x: 1 });

		act(() => {
			vi.advanceTimersByTime(150);
		});
		expect(result.current.target).toBeUndefined();
	});

	it("ignores candidate changes while pinned", () => {
		const { result, rerender } = renderSticky({ id: "a", x: 1 });

		act(() => {
			result.current.pin();
		});
		rerender({ candidate: { id: "b", x: 2 } });
		act(() => {
			vi.advanceTimersByTime(500);
		});
		expect(result.current.target).toEqual({ id: "a", x: 1 });
		expect(result.current.isPinned).toBe(true);

		rerender({ candidate: undefined });
		act(() => {
			vi.advanceTimersByTime(500);
		});
		expect(result.current.target).toEqual({ id: "a", x: 1 });
	});

	it("clears the target immediately when disabled, even while pinned", () => {
		const { result, rerender } = renderSticky({ id: "a", x: 1 });

		act(() => {
			result.current.pin();
		});
		rerender({ candidate: undefined, enabled: false });
		expect(result.current.target).toBeUndefined();
		expect(result.current.isPinned).toBe(false);
	});

	it("resumes following the candidate after unpinning", () => {
		const { result, rerender } = renderSticky({ id: "a", x: 1 });

		act(() => {
			result.current.pin();
		});
		rerender({ candidate: { id: "b", x: 2 } });
		act(() => {
			result.current.unpin();
		});
		expect(result.current.target).toEqual({ id: "a", x: 1 });

		act(() => {
			vi.advanceTimersByTime(150);
		});
		expect(result.current.target).toEqual({ id: "b", x: 2 });
	});
});
