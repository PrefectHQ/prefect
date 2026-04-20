import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useRedirectDetailsTabOnDesktop } from "./use-redirect-details-tab-on-desktop";

type MatchMediaMock = ReturnType<typeof createMatchMediaMock>;

function createMatchMediaMock(isDesktop: boolean) {
	const listeners = new Set<(event: MediaQueryListEvent) => void>();
	const mql = {
		matches: isDesktop,
		media: "(min-width: 1280px)",
		onchange: null,
		addEventListener: vi.fn(
			(_event: "change", listener: (event: MediaQueryListEvent) => void) => {
				listeners.add(listener);
			},
		),
		removeEventListener: vi.fn(
			(_event: "change", listener: (event: MediaQueryListEvent) => void) => {
				listeners.delete(listener);
			},
		),
		dispatchEvent: vi.fn(),
		// Legacy API for completeness
		addListener: vi.fn(),
		removeListener: vi.fn(),
	};
	return {
		mql,
		emitChange(matches: boolean) {
			mql.matches = matches;
			const event = { matches, media: mql.media } as MediaQueryListEvent;
			for (const listener of listeners) {
				listener(event);
			}
		},
	};
}

describe("useRedirectDetailsTabOnDesktop", () => {
	const originalMatchMedia = window.matchMedia;
	let matchMediaMock: MatchMediaMock;

	beforeEach(() => {
		// JSDOM does not resolve Tailwind theme vars, so stub `--breakpoint-xl`
		// on the CSSStyleDeclaration prototype to match Tailwind's default
		// (`80rem`). This keeps the hook's `matchMedia` query in sync with
		// the `xl:hidden` CSS class it coordinates with.
		vi.spyOn(
			CSSStyleDeclaration.prototype,
			"getPropertyValue",
		).mockImplementation((name: string) =>
			name === "--breakpoint-xl" ? "80rem" : "",
		);
	});

	afterEach(() => {
		Object.defineProperty(window, "matchMedia", {
			writable: true,
			configurable: true,
			value: originalMatchMedia,
		});
		vi.restoreAllMocks();
	});

	const mockMatchMedia = (isDesktop: boolean) => {
		matchMediaMock = createMatchMediaMock(isDesktop);
		Object.defineProperty(window, "matchMedia", {
			writable: true,
			configurable: true,
			value: vi.fn().mockReturnValue(matchMediaMock.mql),
		});
	};

	it("does not redirect when the tab is not Details", () => {
		mockMatchMedia(true);
		const redirect = vi.fn();

		renderHook(() => useRedirectDetailsTabOnDesktop("Upcoming Runs", redirect));

		expect(redirect).not.toHaveBeenCalled();
	});

	it("does not redirect when the viewport is narrow", () => {
		mockMatchMedia(false);
		const redirect = vi.fn();

		renderHook(() => useRedirectDetailsTabOnDesktop("Details", redirect));

		expect(redirect).not.toHaveBeenCalled();
	});

	it("redirects when Details is selected on a wide viewport", () => {
		mockMatchMedia(true);
		const redirect = vi.fn();

		renderHook(() => useRedirectDetailsTabOnDesktop("Details", redirect));

		expect(redirect).toHaveBeenCalledTimes(1);
	});

	it("redirects when the viewport grows past the xl breakpoint", () => {
		mockMatchMedia(false);
		const redirect = vi.fn();

		renderHook(() => useRedirectDetailsTabOnDesktop("Details", redirect));

		expect(redirect).not.toHaveBeenCalled();

		matchMediaMock.emitChange(true);

		expect(redirect).toHaveBeenCalledTimes(1);
	});

	it("cleans up the media query listener on unmount", () => {
		mockMatchMedia(false);
		const redirect = vi.fn();

		const { unmount } = renderHook(() =>
			useRedirectDetailsTabOnDesktop("Details", redirect),
		);

		expect(matchMediaMock.mql.addEventListener).toHaveBeenCalledTimes(1);
		unmount();
		expect(matchMediaMock.mql.removeEventListener).toHaveBeenCalledTimes(1);
	});

	it("is a no-op when the breakpoint CSS variable is missing", () => {
		vi.spyOn(
			CSSStyleDeclaration.prototype,
			"getPropertyValue",
		).mockImplementation(() => "");
		mockMatchMedia(true);
		const redirect = vi.fn();

		renderHook(() => useRedirectDetailsTabOnDesktop("Details", redirect));

		expect(redirect).not.toHaveBeenCalled();
	});
});
