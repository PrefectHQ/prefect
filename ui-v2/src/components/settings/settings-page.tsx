import { useSuspenseQuery } from "@tanstack/react-query";
import { useState } from "react";
import { buildGetSettingsQuery, buildGetVersionQuery } from "@/api/admin";
import { buildUiSettingsQuery } from "@/api/ui-settings";
import {
	switchToV1Ui,
	UiVersionSwitchCard,
	UiVersionSwitchDialog,
	type UiVersionSwitchDialogValues,
} from "@/components/ui-version-switch";
import { usePageTitle } from "@/hooks/use-page-title";
import { isUiAvailable } from "@/utils/ui-version";

import { ColorModeSelect } from "./color-mode-select";
import { Heading } from "./heading";
import { ServerSettings } from "./server-settings";
import { ThemeSwitch } from "./theme-switch";

export const SettingsPage = () => {
	usePageTitle("Settings");
	const [isSwitchDialogOpen, setIsSwitchDialogOpen] = useState(false);
	const { data: settingsData } = useSuspenseQuery(buildGetSettingsQuery());
	const { data: versionData } = useSuspenseQuery(buildGetVersionQuery());
	const { data: browserUiSettings } = useSuspenseQuery(buildUiSettingsQuery());
	const analyticsEnabled =
		(settingsData as { server?: { analytics_enabled?: boolean } }).server
			?.analytics_enabled ?? true;
	const canSwitchToV1 =
		isUiAvailable(browserUiSettings.availableUis ?? [], "v1") &&
		Boolean(browserUiSettings.v1BaseUrl);

	const handleSwitchToV1 = (feedback?: UiVersionSwitchDialogValues) => {
		switchToV1Ui({
			uiSettings: browserUiSettings,
			analyticsEnabled,
			feedback,
		});
	};

	return (
		<div className="flex flex-col gap-4">
			<Heading version={versionData} />
			<ThemeSwitch />
			<ColorModeSelect />
			{canSwitchToV1 && (
				<UiVersionSwitchCard onSwitch={() => setIsSwitchDialogOpen(true)} />
			)}
			{/** nb: open API needs to update schema */}
			<ServerSettings settings={settingsData as Record<string, unknown>} />
			<UiVersionSwitchDialog
				open={isSwitchDialogOpen}
				onOpenChange={setIsSwitchDialogOpen}
				onSkipFeedback={() => handleSwitchToV1()}
				onSubmitFeedback={(values) => handleSwitchToV1(values)}
			/>
		</div>
	);
};
