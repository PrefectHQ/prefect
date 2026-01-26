import { useQuery } from "@tanstack/react-query";
import { type ReactNode, useEffect, useRef } from "react";
import { buildGetSettingsQuery } from "@/api/admin";
import { initAmplitude, trackV2UIUsed } from "./index";

type ServerSettings = {
	server?: {
		analytics_enabled?: boolean;
	};
};

export function AnalyticsProvider({ children }: { children: ReactNode }) {
	const amplitudeInitialized = useRef(false);
	const trackingAttempted = useRef(false);

	useEffect(() => {
		if (!amplitudeInitialized.current) {
			amplitudeInitialized.current = initAmplitude();
		}
	}, []);

	const { data: settings } = useQuery({
		...buildGetSettingsQuery(),
		enabled: amplitudeInitialized.current,
	});

	useEffect(() => {
		if (!amplitudeInitialized.current || trackingAttempted.current) {
			return;
		}

		if (settings) {
			trackingAttempted.current = true;
			const serverSettings = settings as ServerSettings;
			const analyticsEnabled = serverSettings.server?.analytics_enabled ?? true;
			trackV2UIUsed(analyticsEnabled);
		}
	}, [settings]);

	return <>{children}</>;
}
