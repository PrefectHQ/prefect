import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { usePageTitle } from "./use-page-title";

describe("usePageTitle", () => {
	const originalTitle = document.title;

	beforeEach(() => {
		document.title = "Initial Title";
	});

	afterEach(() => {
		document.title = originalTitle;
	});

	it("sets document.title correctly with a single segment", () => {
		renderHook(() => usePageTitle("Dashboard"));

		expect(document.title).toBe("Dashboard • Prefect Server");
	});

	it("sets document.title correctly with multiple segments", () => {
		renderHook(() => usePageTitle("Flow", "MyFlow"));

		expect(document.title).toBe("Flow • MyFlow • Prefect Server");
	});

	it("filters out null values from segments", () => {
		renderHook(() => usePageTitle(null, "Flow"));

		expect(document.title).toBe("Flow • Prefect Server");
	});

	it("filters out undefined values from segments", () => {
		renderHook(() => usePageTitle(undefined, "Flow"));

		expect(document.title).toBe("Flow • Prefect Server");
	});

	it("filters out multiple null and undefined values", () => {
		renderHook(() => usePageTitle(null, "Flow", undefined, "Details", null));

		expect(document.title).toBe("Flow • Details • Prefect Server");
	});

	it("always appends 'Prefect Server' suffix", () => {
		renderHook(() => usePageTitle("Test"));

		expect(document.title).toContain("Prefect Server");
		expect(document.title.endsWith("Prefect Server")).toBe(true);
	});

	it("sets title to just 'Prefect Server' when all segments are null/undefined", () => {
		renderHook(() => usePageTitle(null, undefined));

		expect(document.title).toBe("Prefect Server");
	});

	it("sets title to just 'Prefect Server' when no segments provided", () => {
		renderHook(() => usePageTitle());

		expect(document.title).toBe("Prefect Server");
	});

	it("updates title when arguments change", () => {
		const { rerender } = renderHook(
			({ segments }) => usePageTitle(...segments),
			{ initialProps: { segments: ["Flow"] as (string | null | undefined)[] } },
		);

		expect(document.title).toBe("Flow • Prefect Server");

		rerender({ segments: ["Flow", "MyFlow"] });

		expect(document.title).toBe("Flow • MyFlow • Prefect Server");
	});

	it("updates title when conditional value changes from undefined to string", () => {
		const { rerender } = renderHook(
			({ name }) => usePageTitle(name ? `Flow: ${name}` : "Flow"),
			{ initialProps: { name: undefined as string | undefined } },
		);

		expect(document.title).toBe("Flow • Prefect Server");

		rerender({ name: "MyFlow" });

		expect(document.title).toBe("Flow: MyFlow • Prefect Server");
	});

	it("resets title to 'Prefect Server' on unmount", () => {
		const { unmount } = renderHook(() => usePageTitle("Dashboard"));

		expect(document.title).toBe("Dashboard • Prefect Server");

		act(() => {
			unmount();
		});

		expect(document.title).toBe("Prefect Server");
	});

	it("handles complex title with Flow prefix pattern", () => {
		renderHook(() => usePageTitle("Flow: my-etl-pipeline"));

		expect(document.title).toBe("Flow: my-etl-pipeline • Prefect Server");
	});
});
