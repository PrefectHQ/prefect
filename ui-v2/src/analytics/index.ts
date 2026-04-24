import * as amplitude from "@amplitude/analytics-browser";
import type { UiSwitchReason, UiVersion } from "@/utils/ui-version";

const SESSION_STORAGE_KEY = "prefect-web-app-loaded";

function getAmplitudeApiKey(): string | undefined {
	return import.meta.env.VITE_AMPLITUDE_API_KEY as string | undefined;
}

export function initAmplitude(): boolean {
	const amplitudeApiKey = getAmplitudeApiKey();
	if (!amplitudeApiKey) {
		return false;
	}

	amplitude.init(amplitudeApiKey, {
		trackingOptions: {
			ipAddress: false,
			language: false,
			platform: false,
		},
		autocapture: false,
	});

	return true;
}

export type WebAppLoadedEventProperties = {
	environment: string;
	prefect_version: string;
};

export function trackWebAppLoaded(
	analyticsEnabled: boolean,
	properties: WebAppLoadedEventProperties,
): void {
	if (!getAmplitudeApiKey()) {
		return;
	}

	if (!analyticsEnabled) {
		return;
	}

	const alreadyTracked = sessionStorage.getItem(SESSION_STORAGE_KEY);
	if (alreadyTracked) {
		return;
	}

	amplitude.track("Web App Loaded", properties);
	sessionStorage.setItem(SESSION_STORAGE_KEY, "true");
}

type UiVersionSwitchedEventProperties = {
	from_ui: UiVersion;
	to_ui: UiVersion;
	current_path: string;
};

type UiSwitchFeedbackSubmittedEventProperties =
	UiVersionSwitchedEventProperties & {
		reason: UiSwitchReason;
		has_notes: boolean;
	};

function trackAnalyticsEvent(
	analyticsEnabled: boolean,
	eventName: string,
	properties: Record<string, unknown>,
): void {
	if (!getAmplitudeApiKey() || !analyticsEnabled) {
		return;
	}

	amplitude.track(eventName, properties);
}

export function trackUiVersionSwitched(
	analyticsEnabled: boolean,
	properties: UiVersionSwitchedEventProperties,
): void {
	trackAnalyticsEvent(analyticsEnabled, "UI Version Switched", properties);
}

export function trackUiSwitchFeedbackSubmitted(
	analyticsEnabled: boolean,
	properties: UiSwitchFeedbackSubmittedEventProperties,
): void {
	trackAnalyticsEvent(
		analyticsEnabled,
		"UI Switch Feedback Submitted",
		properties,
	);
}
