/* eslint-disable @typescript-eslint/unbound-method */
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useColorMode } from "./use-color-mode";

describe("useColorMode", () => {
	beforeEach(() => {
		vi.mocked(localStorage.getItem).mockReturnValue(null);
		vi.mocked(localStorage.setItem).mockClear();
		document.body.className = "";
	});

	it("defaults to 'default' color mode", () => {
		const { result } = renderHook(() => useColorMode());
		expect(result.current.colorMode).toBe("default");
	});

	it("applies color mode class to document.body", () => {
		renderHook(() => useColorMode());
		expect(document.body.classList.contains("color-mode-default")).toBe(true);
	});

	it("changes color mode and updates class", () => {
		const { result } = renderHook(() => useColorMode());
		act(() => {
			result.current.setColorMode("deuteranopia");
		});
		expect(result.current.colorMode).toBe("deuteranopia");
		expect(document.body.classList.contains("color-mode-deuteranopia")).toBe(
			true,
		);
		expect(document.body.classList.contains("color-mode-default")).toBe(false);
	});

	it("persists color mode in localStorage", () => {
		const { result } = renderHook(() => useColorMode());
		act(() => {
			result.current.setColorMode("protanomaly");
		});
		expect(localStorage.setItem).toBeCalledWith(
			"prefect-color-mode",
			'"protanomaly"',
		);
	});

	it("restores color mode from localStorage on mount", () => {
		vi.mocked(localStorage.getItem).mockReturnValue('"tritanopia"');
		const { result } = renderHook(() => useColorMode());
		expect(result.current.colorMode).toBe("tritanopia");
		expect(document.body.classList.contains("color-mode-tritanopia")).toBe(
			true,
		);
	});

	it("exposes all available color modes", () => {
		const { result } = renderHook(() => useColorMode());
		expect(result.current.colorModes).toEqual([
			"default",
			"achromatopsia",
			"deuteranopia",
			"deuteranomaly",
			"protanopia",
			"protanomaly",
			"tritanomaly",
			"tritanopia",
			"high-contrast",
			"low-contrast",
		]);
	});
});
