import { useQueries } from "@tanstack/react-query";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { buildGetSettingsQuery, buildGetVersionQuery } from "@/api/admin";
import { initAmplitude, trackWebAppLoaded } from "./index";

type ServerSettings = {
	server?: {
		analytics_enabled?: boolean;
	};
};

export function AnalyticsProvider({ children }: { children: ReactNode }) {
	const [amplitudeInitialized, setAmplitudeInitialized] = useState(false);
	const trackingAttempted = useRef(false);

	useEffect(() => {
		if (!amplitudeInitialized) {
			setAmplitudeInitialized(initAmplitude());
		}
	}, [amplitudeInitialized]);

	const [{ data: settings }, { data: version }] = useQueries({
		queries: [
			{ ...buildGetSettingsQuery(), enabled: amplitudeInitialized },
			{ ...buildGetVersionQuery(), enabled: amplitudeInitialized },
		],
	});

	useEffect(() => {
		if (!amplitudeInitialized || trackingAttempted.current) {
			return;
		}

		if (settings && version) {
			trackingAttempted.current = true;
			const serverSettings = settings as ServerSettings;
			const analyticsEnabled = serverSettings.server?.analytics_enabled ?? true;
			trackWebAppLoaded(analyticsEnabled, {
				environment: "OSS",
				prefect_version: version,
			});
		}
	}, [amplitudeInitialized, settings, version]);

	return <>{children}</>;
}
