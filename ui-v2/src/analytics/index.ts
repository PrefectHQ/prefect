import * as amplitude from "@amplitude/analytics-browser";

const AMPLITUDE_API_KEY = import.meta.env.VITE_AMPLITUDE_API_KEY;
const SESSION_STORAGE_KEY = "prefect-v2-ui-tracked";

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

export function trackV2UIUsed(analyticsEnabled: boolean): void {
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

	amplitude.track("V2 UI Used");
	sessionStorage.setItem(SESSION_STORAGE_KEY, "true");
}
