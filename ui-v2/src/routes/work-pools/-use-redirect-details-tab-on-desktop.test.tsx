import { renderHook } from "@testing-library/react";
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useRedirectDetailsTabOnDesktop } from "./-use-redirect-details-tab-on-desktop";

type MatchMediaMock = ReturnType<typeof createMatchMediaMock>;

function createMatchMediaMock(isDesktop: boolean) {
	const listeners = new Set<(event: MediaQueryListEvent) => void>();
	const mql = {
		matches: isDesktop,
		media: "(min-width: 1024px)",
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
		// JSDOM does not resolve Tailwind theme vars, so stub `--breakpoint-lg`
		// on the CSSStyleDeclaration prototype to match Tailwind's default
		// (`64rem`). This keeps the hook's `matchMedia` query in sync with the
		// `lg:hidden` CSS class it coordinates with.
		vi.spyOn(
			CSSStyleDeclaration.prototype,
			"getPropertyValue",
		).mockImplementation((name: string) =>
			name === "--breakpoint-lg" ? "64rem" : "",
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

	it("does not redirect when tab is not Details", () => {
		mockMatchMedia(true);
		const navigate = vi.fn();
		renderHook(() =>
			useRedirectDetailsTabOnDesktop({
				tab: "Runs",
				fallbackTab: "Runs",
				navigate,
			}),
		);
		expect(navigate).not.toHaveBeenCalled();
	});

	it("does not redirect when tab is Details on a narrow viewport", () => {
		mockMatchMedia(false);
		const navigate = vi.fn();
		renderHook(() =>
			useRedirectDetailsTabOnDesktop({
				tab: "Details",
				fallbackTab: "Runs",
				navigate,
			}),
		);
		expect(navigate).not.toHaveBeenCalled();
	});

	it("redirects Details to the fallback tab on a wide viewport", () => {
		mockMatchMedia(true);
		const navigate = vi.fn();
		renderHook(() =>
			useRedirectDetailsTabOnDesktop({
				tab: "Details",
				fallbackTab: "Runs",
				navigate,
			}),
		);
		expect(navigate).toHaveBeenCalledWith("Runs");
	});

	it("redirects Details to the fallback tab when viewport crosses the lg breakpoint", () => {
		mockMatchMedia(false);
		const navigate = vi.fn();
		renderHook(() =>
			useRedirectDetailsTabOnDesktop({
				tab: "Details",
				fallbackTab: "Runs",
				navigate,
			}),
		);
		expect(navigate).not.toHaveBeenCalled();

		act(() => {
			matchMediaMock.emitChange(true);
		});

		expect(navigate).toHaveBeenCalledWith("Runs");
	});

	it("does nothing when --breakpoint-lg is not defined on the document", () => {
		vi.spyOn(
			CSSStyleDeclaration.prototype,
			"getPropertyValue",
		).mockImplementation(() => "");
		const matchMediaSpy = vi.fn();
		Object.defineProperty(window, "matchMedia", {
			writable: true,
			configurable: true,
			value: matchMediaSpy,
		});
		const navigate = vi.fn();
		renderHook(() =>
			useRedirectDetailsTabOnDesktop({
				tab: "Details",
				fallbackTab: "Runs",
				navigate,
			}),
		);
		expect(matchMediaSpy).not.toHaveBeenCalled();
		expect(navigate).not.toHaveBeenCalled();
	});
});
