import * as amplitude from "@amplitude/analytics-browser";

const AMPLITUDE_API_KEY = import.meta.env.VITE_AMPLITUDE_API_KEY;
const SESSION_STORAGE_KEY = "prefect-web-app-loaded";

export function initAmplitude(): boolean {
	if (!AMPLITUDE_API_KEY) {
		return false;
	}

	amplitude.init(AMPLITUDE_API_KEY, {
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
	if (!AMPLITUDE_API_KEY) {
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
