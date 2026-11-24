import { mockBrowserTimezone } from "@tests/utils/browser";
import { afterEach, describe, expect, test, vi } from "vitest";
import { getLocalTimezone } from "./date";

describe("getLocalTimezone", () => {
	afterEach(() => {
		vi.restoreAllMocks();
	});

	test("returns the browser time zone", () => {
		mockBrowserTimezone("America/Chicago");

		expect(getLocalTimezone()).toBe("America/Chicago");
	});

	test("falls back to UTC when the browser reports no time zone", () => {
		mockBrowserTimezone(undefined);

		expect(getLocalTimezone()).toBe("UTC");
	});

	test("falls back to UTC when resolving the time zone throws", () => {
		vi.spyOn(
			Intl.DateTimeFormat.prototype,
			"resolvedOptions",
		).mockImplementation(() => {
			throw new RangeError("Invalid time zone");
		});

		expect(getLocalTimezone()).toBe("UTC");
	});
});
