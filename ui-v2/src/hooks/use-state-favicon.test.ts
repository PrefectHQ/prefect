import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useStateFavicon } from "./use-state-favicon";

type FaviconArg = Parameters<typeof useStateFavicon>[0];

describe("useStateFavicon", () => {
	let favicon16: HTMLLinkElement;
	let favicon32: HTMLLinkElement;
	let favicon16Dark: HTMLLinkElement;
	let favicon32Dark: HTMLLinkElement;
	const originalMatchMedia = window.matchMedia;

	const createMatchMediaMock = (prefersDark: boolean) => {
		return vi.fn().mockImplementation((query: string) => ({
			matches:
				prefersDark === true
					? query === "(prefers-color-scheme: dark)"
					: query === "(prefers-color-scheme: light)",
			media: query,
			onchange: null,
			addListener: vi.fn(),
			removeListener: vi.fn(),
			addEventListener: vi.fn(),
			removeEventListener: vi.fn(),
			dispatchEvent: vi.fn(),
		})) as unknown as typeof window.matchMedia;
	};

	beforeEach(() => {
		// Create mock favicon elements
		favicon16 = document.createElement("link");
		favicon16.id = "favicon-16";
		favicon16.setAttribute("href", "/favicon-16x16.png");
		document.head.appendChild(favicon16);

		favicon32 = document.createElement("link");
		favicon32.id = "favicon-32";
		favicon32.setAttribute("href", "/favicon-32x32.png");
		document.head.appendChild(favicon32);

		favicon16Dark = document.createElement("link");
		favicon16Dark.id = "favicon-16-dark";
		favicon16Dark.setAttribute("href", "/favicon-16x16-dark.png");
		document.head.appendChild(favicon16Dark);

		favicon32Dark = document.createElement("link");
		favicon32Dark.id = "favicon-32-dark";
		favicon32Dark.setAttribute("href", "/favicon-32x32-dark.png");
		document.head.appendChild(favicon32Dark);

		// Mock matchMedia to return light mode by default
		Object.defineProperty(window, "matchMedia", {
			writable: true,
			value: createMatchMediaMock(false),
		});
	});

	afterEach(() => {
		// Clean up favicon elements
		favicon16.remove();
		favicon32.remove();
		favicon16Dark.remove();
		favicon32Dark.remove();
		// Restore original matchMedia
		Object.defineProperty(window, "matchMedia", {
			writable: true,
			value: originalMatchMedia,
		});
		vi.restoreAllMocks();
	});

	it("sets favicon to state-specific SVG when stateType is provided", () => {
		renderHook(() => useStateFavicon("COMPLETED"));

		expect(favicon16.getAttribute("href")).toBe("/completed.svg");
		expect(favicon32.getAttribute("href")).toBe("/completed.svg");
	});

	it("converts state type to lowercase for favicon path", () => {
		renderHook(() => useStateFavicon("FAILED"));

		expect(favicon16.getAttribute("href")).toBe("/failed.svg");
		expect(favicon32.getAttribute("href")).toBe("/failed.svg");
	});

	it("does not change favicon when stateType is null", () => {
		renderHook(() => useStateFavicon(null));

		expect(favicon16.getAttribute("href")).toBe("/favicon-16x16.png");
		expect(favicon32.getAttribute("href")).toBe("/favicon-32x32.png");
	});

	it("does not change favicon when stateType is undefined", () => {
		renderHook(() => useStateFavicon(undefined));

		expect(favicon16.getAttribute("href")).toBe("/favicon-16x16.png");
		expect(favicon32.getAttribute("href")).toBe("/favicon-32x32.png");
	});

	it("resets favicon to default on unmount in light mode", () => {
		const { unmount } = renderHook(() => useStateFavicon("RUNNING"));

		expect(favicon16.getAttribute("href")).toBe("/running.svg");
		expect(favicon32.getAttribute("href")).toBe("/running.svg");

		act(() => {
			unmount();
		});

		expect(favicon16.getAttribute("href")).toBe("/favicon-16x16.png");
		expect(favicon32.getAttribute("href")).toBe("/favicon-32x32.png");
	});

	it("uses dark favicon elements when prefers-color-scheme is dark", () => {
		// Mock dark mode
		Object.defineProperty(window, "matchMedia", {
			writable: true,
			value: createMatchMediaMock(true),
		});

		renderHook(() => useStateFavicon("SCHEDULED"));

		expect(favicon16Dark.getAttribute("href")).toBe("/scheduled.svg");
		expect(favicon32Dark.getAttribute("href")).toBe("/scheduled.svg");
	});

	it("resets to dark favicon on unmount when in dark mode", () => {
		// Mock dark mode
		Object.defineProperty(window, "matchMedia", {
			writable: true,
			value: createMatchMediaMock(true),
		});

		const { unmount } = renderHook(() => useStateFavicon("CRASHED"));

		expect(favicon16Dark.getAttribute("href")).toBe("/crashed.svg");
		expect(favicon32Dark.getAttribute("href")).toBe("/crashed.svg");

		act(() => {
			unmount();
		});

		expect(favicon16Dark.getAttribute("href")).toBe("/favicon-16x16-dark.png");
		expect(favicon32Dark.getAttribute("href")).toBe("/favicon-32x32-dark.png");
	});

	it("updates favicon when stateType changes", () => {
		const { rerender } = renderHook(
			({ stateType }: { stateType: FaviconArg }) => useStateFavicon(stateType),
			{ initialProps: { stateType: "PENDING" } },
		);

		expect(favicon16.getAttribute("href")).toBe("/pending.svg");
		expect(favicon32.getAttribute("href")).toBe("/pending.svg");

		rerender({ stateType: "COMPLETED" });

		expect(favicon16.getAttribute("href")).toBe("/completed.svg");
		expect(favicon32.getAttribute("href")).toBe("/completed.svg");
	});

	it("handles all state types correctly", () => {
		const stateTypes = [
			"SCHEDULED",
			"PENDING",
			"RUNNING",
			"COMPLETED",
			"FAILED",
			"CANCELLED",
			"CANCELLING",
			"CRASHED",
			"PAUSED",
		] as const;

		for (const stateType of stateTypes) {
			const { unmount } = renderHook(() => useStateFavicon(stateType));

			expect(favicon16.getAttribute("href")).toBe(
				`/${stateType.toLowerCase()}.svg`,
			);
			expect(favicon32.getAttribute("href")).toBe(
				`/${stateType.toLowerCase()}.svg`,
			);

			act(() => {
				unmount();
			});
		}
	});

	it("handles no-preference color scheme by using light mode favicons", () => {
		// Mock no-preference (neither dark nor light matches)
		Object.defineProperty(window, "matchMedia", {
			writable: true,
			value: vi.fn().mockImplementation(() => ({
				matches: false,
				media: "",
				onchange: null,
				addListener: vi.fn(),
				removeListener: vi.fn(),
				addEventListener: vi.fn(),
				removeEventListener: vi.fn(),
				dispatchEvent: vi.fn(),
			})) as unknown as typeof window.matchMedia,
		});

		renderHook(() => useStateFavicon("FAILED"));

		// Should use light mode favicons (favicon-16, favicon-32)
		expect(favicon16.getAttribute("href")).toBe("/failed.svg");
		expect(favicon32.getAttribute("href")).toBe("/failed.svg");
	});
});
