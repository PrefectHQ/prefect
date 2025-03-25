import { buildGetSettingsQuery, buildGetVersionQuery } from "@/api/admin";
import { SettingsPage } from "@/components/settings/settings-page";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/settings")({
	component: SettingsPage,
	loader: ({ context }) =>
		Promise.all([
			context.queryClient.ensureQueryData(buildGetSettingsQuery()),
			context.queryClient.ensureQueryData(buildGetVersionQuery()),
		]),
	wrapInSuspense: true,
});
