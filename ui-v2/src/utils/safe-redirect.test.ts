import { describe, expect, it } from "vitest";
import { isSafeRedirectPath } from "./safe-redirect";

describe("isSafeRedirectPath", () => {
	it.each([
		"/dashboard",
		"/flows?x=1",
		"/flow-runs/flow-run/abc?tab=Logs#top",
		"/flows/%2F%2Fevil.example",
		"/",
	])("accepts same-origin path %j", (value) => {
		expect(isSafeRedirectPath(value)).toBe(true);
	});

	it.each([
		"https://evil.example/phish",
		"http://evil.example",
		"//evil.example/phish",
		"/\\evil.example",
		"\\\\evil.example",
		"/\t/evil.example",
		"/\n/evil.example",
		"javascript:alert(1)",
		"data:text/html,hi",
		"dashboard",
		" /dashboard",
		"",
	])("rejects %j", (value) => {
		expect(isSafeRedirectPath(value)).toBe(false);
	});
});
