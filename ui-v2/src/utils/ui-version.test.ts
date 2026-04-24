import { describe, expect, it } from "vitest";
import {
	buildSwitchToV1Url,
	buildUiSwitchGithubIssueUrl,
	getUiPathPrefix,
	normalizeBasePath,
	resolveVisibleUiBasePath,
	stripV2BasePath,
} from "./ui-version";

describe("ui-version utils", () => {
	it("normalizes router base paths", () => {
		expect(normalizeBasePath("")).toBe("/");
		expect(normalizeBasePath("/v2/")).toBe("/v2");
		expect(normalizeBasePath("prefect/v2")).toBe("/prefect/v2");
	});

	it("derives the settings base path from the app base path", () => {
		expect(stripV2BasePath("/v2")).toBe("/");
		expect(stripV2BasePath("/prefect/v2")).toBe("/prefect");
		expect(stripV2BasePath("/prefect")).toBe("/prefect");
	});

	it("builds the V2 to V1 counterpart URL", () => {
		expect(
			buildSwitchToV1Url({
				v1BaseUrl: "/prefect",
				v2BaseUrl: "/prefect/v2",
				location: {
					pathname: "/prefect/v2/settings",
					search: "?tab=ui",
					hash: "#feedback",
				},
			}),
		).toBe("/prefect/settings?tab=ui#feedback");
	});

	it("preserves proxy prefixes when resolving visible UI base paths", () => {
		expect(getUiPathPrefix("/proxy/prefect/v2/settings", "/prefect/v2")).toBe(
			"/proxy",
		);
		expect(
			getUiPathPrefix("/company/v2/prefect/v2/settings", "/v2"),
		).toBe("/company/v2/prefect");
		expect(
			resolveVisibleUiBasePath({
				configuredBasePath: "/prefect",
				currentBasePath: "/prefect/v2",
				location: {
					pathname: "/proxy/prefect/v2/settings",
				},
			}),
		).toBe("/proxy/prefect");
		expect(
			resolveVisibleUiBasePath({
				configuredBasePath: "/v2",
				currentBasePath: "/v2",
				location: {
					pathname: "/company/v2/prefect/v2/settings",
				},
			}),
		).toBe("/company/v2/prefect/v2");
	});

	it("builds proxied V2 to V1 counterpart URLs", () => {
		expect(
			buildSwitchToV1Url({
				v1BaseUrl: "/prefect",
				v2BaseUrl: "/prefect/v2",
				location: {
					pathname: "/proxy/prefect/v2/settings",
					search: "?tab=ui",
					hash: "#feedback",
				},
			}),
		).toBe("/proxy/prefect/settings?tab=ui#feedback");
	});

	it("builds a prefilled GitHub issue URL", () => {
		const issueUrl = buildUiSwitchGithubIssueUrl({
			reason: "missing_feature",
			notes: "Need the old flow graph.",
			currentPath: "/runs/123",
		});

		expect(issueUrl).toContain(
			"https://github.com/PrefectHQ/prefect/issues/new?",
		);
		expect(issueUrl).toContain("New+UI+feedback%3A+Missing+feature");
		expect(issueUrl).toContain("%2Fruns%2F123");
		expect(issueUrl).toContain("Need+the+old+flow+graph.");
	});
});
