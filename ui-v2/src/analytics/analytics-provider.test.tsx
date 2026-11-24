import * as amplitude from "@amplitude/analytics-browser";
import { render, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createFakeServerSettings } from "@/mocks";
import { AnalyticsProvider } from "./analytics-provider";

const mockServerSettings = (analyticsEnabled: boolean) => {
	const settingsRequested = vi.fn();
	server.use(
		http.get(buildApiUrl("/admin/settings"), () => {
			settingsRequested();
			return HttpResponse.json(
				createFakeServerSettings({
					server: { analytics_enabled: analyticsEnabled },
				}),
			);
		}),
		http.get(buildApiUrl("/admin/version"), () => {
			return HttpResponse.json("3.0.0");
		}),
	);
	return settingsRequested;
};

describe("AnalyticsProvider", () => {
	beforeEach(() => {
		vi.stubEnv("VITE_AMPLITUDE_API_KEY", "test-key");
		vi.mocked(amplitude.init).mockClear();
		vi.mocked(amplitude.track).mockClear();
		sessionStorage.clear();
	});

	afterEach(() => {
		vi.unstubAllEnvs();
	});

	it("initializes Amplitude and tracks the app load when analytics are enabled", async () => {
		mockServerSettings(true);

		render(<AnalyticsProvider>content</AnalyticsProvider>, {
			wrapper: createWrapper(),
		});

		await waitFor(() =>
			expect(vi.mocked(amplitude.track)).toHaveBeenCalledWith(
				"Web App Loaded",
				{ environment: "OSS", prefect_version: "3.0.0" },
			),
		);
		expect(vi.mocked(amplitude.init)).toHaveBeenCalledTimes(1);
	});

	it("does not initialize Amplitude when analytics are disabled", async () => {
		const settingsRequested = mockServerSettings(false);

		render(<AnalyticsProvider>content</AnalyticsProvider>, {
			wrapper: createWrapper(),
		});

		await waitFor(() => expect(settingsRequested).toHaveBeenCalled());
		await new Promise((resolve) => setTimeout(resolve, 50));
		expect(vi.mocked(amplitude.init)).not.toHaveBeenCalled();
		expect(vi.mocked(amplitude.track)).not.toHaveBeenCalled();
	});

	it("does not request server settings when no Amplitude API key is configured", async () => {
		vi.stubEnv("VITE_AMPLITUDE_API_KEY", "");
		const settingsRequested = mockServerSettings(true);

		render(<AnalyticsProvider>content</AnalyticsProvider>, {
			wrapper: createWrapper(),
		});

		await new Promise((resolve) => setTimeout(resolve, 50));
		expect(settingsRequested).not.toHaveBeenCalled();
		expect(vi.mocked(amplitude.init)).not.toHaveBeenCalled();
	});
});
