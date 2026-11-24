import { useQuery } from "@tanstack/react-query";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { buildGetSettingsQuery, buildGetVersionQuery } from "@/api/admin";
import {
	initAmplitude,
	isAmplitudeConfigured,
	trackWebAppLoaded,
} from "./index";

type ServerSettings = {
	server?: {
		analytics_enabled?: boolean;
	};
};

export function AnalyticsProvider({ children }: { children: ReactNode }) {
	const [amplitudeInitialized, setAmplitudeInitialized] = useState(false);
	const trackingAttempted = useRef(false);

	const { data: settings } = useQuery({
		...buildGetSettingsQuery(),
		enabled: isAmplitudeConfigured(),
	});
	const analyticsEnabled =
		(settings as ServerSettings | undefined)?.server?.analytics_enabled ??
		false;

	useEffect(() => {
		if (analyticsEnabled && !amplitudeInitialized) {
			setAmplitudeInitialized(initAmplitude());
		}
	}, [analyticsEnabled, amplitudeInitialized]);

	const { data: version } = useQuery({
		...buildGetVersionQuery(),
		enabled: amplitudeInitialized,
	});

	useEffect(() => {
		if (!amplitudeInitialized || trackingAttempted.current || !version) {
			return;
		}

		trackingAttempted.current = true;
		trackWebAppLoaded(analyticsEnabled, {
			environment: "OSS",
			prefect_version: version,
		});
	}, [amplitudeInitialized, analyticsEnabled, version]);

	return <>{children}</>;
}
