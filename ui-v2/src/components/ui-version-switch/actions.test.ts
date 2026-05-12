import * as amplitude from "@amplitude/analytics-browser";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { switchToV1Ui } from "./actions";

describe("switchToV1Ui", () => {
	beforeEach(() => {
		vi.stubEnv("VITE_AMPLITUDE_API_KEY", "test-key");
		vi.mocked(amplitude.track).mockClear();
		document.cookie = "prefect_ui_version=; Max-Age=0; Path=/; SameSite=Lax";
	});

	afterEach(() => {
		vi.unstubAllEnvs();
	});

	it("tracks both switch events, opens GitHub, and redirects", () => {
		const openWindow = vi.fn();
		const redirectTo = vi.fn();

		const targetUrl = switchToV1Ui({
			uiSettings: {
				v1BaseUrl: "/",
				v2BaseUrl: "/v2",
			},
			analyticsEnabled: true,
			location: {
				pathname: "/v2/settings",
				search: "?tab=ui",
				hash: "#feedback",
			},
			feedback: {
				reason: "missing_feature",
				notes: "Need the old flow graph.",
				openGithubIssue: true,
			},
			openWindow,
			redirectTo,
		});

		expect(targetUrl).toBe("/settings?tab=ui#feedback");
		expect(document.cookie).toContain("prefect_ui_version=v1");
		expect(vi.mocked(amplitude.track)).toHaveBeenCalledTimes(2);
		expect(vi.mocked(amplitude.track)).toHaveBeenNthCalledWith(
			1,
			"UI Version Switched",
			{
				from_ui: "v2",
				to_ui: "v1",
				current_path: "/settings",
			},
		);
		expect(vi.mocked(amplitude.track)).toHaveBeenNthCalledWith(
			2,
			"UI Switch Feedback Submitted",
			{
				reason: "missing_feature",
				has_notes: true,
				from_ui: "v2",
				to_ui: "v1",
				current_path: "/settings",
			},
		);
		expect(openWindow).toHaveBeenCalledWith(
			expect.stringContaining("issues/new?"),
			"_blank",
			"noopener,noreferrer",
		);
		expect(redirectTo).toHaveBeenCalledWith("/settings?tab=ui#feedback");
	});

	it("skips analytics and GitHub when analytics are disabled and no feedback is provided", () => {
		const redirectTo = vi.fn();

		switchToV1Ui({
			uiSettings: {
				v1BaseUrl: "/",
				v2BaseUrl: "/v2",
			},
			analyticsEnabled: false,
			location: {
				pathname: "/v2/dashboard",
			},
			redirectTo,
		});

		expect(vi.mocked(amplitude.track)).not.toHaveBeenCalled();
		expect(redirectTo).toHaveBeenCalledWith("/dashboard");
	});

	it("preserves proxy prefixes when switching from V2 to V1", () => {
		const redirectTo = vi.fn();

		switchToV1Ui({
			uiSettings: {
				v1BaseUrl: "/prefect",
				v2BaseUrl: "/prefect/v2",
			},
			analyticsEnabled: false,
			location: {
				pathname: "/proxy/prefect/v2/dashboard",
			},
			redirectTo,
		});

		expect(redirectTo).toHaveBeenCalledWith("/proxy/prefect/dashboard");
	});
});
