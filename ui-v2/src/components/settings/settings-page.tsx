import { useSuspenseQuery } from "@tanstack/react-query";
import { buildGetSettingsQuery, buildGetVersionQuery } from "@/api/admin";

import { ColorModeSelect } from "./color-mode-select";
import { Heading } from "./heading";
import { ServerSettings } from "./server-settings";
import { ThemeSwitch } from "./theme-switch";

export const SettingsPage = () => {
	const { data: settingsData } = useSuspenseQuery(buildGetSettingsQuery());
	const { data: versionData } = useSuspenseQuery(buildGetVersionQuery());

	return (
		<div className="flex flex-col gap-4">
			<Heading version={versionData} />
			<ThemeSwitch />
			<ColorModeSelect />
			{/** nb: open API needs to update schema */}
			<ServerSettings settings={settingsData as Record<string, unknown>} />
		</div>
	);
};
