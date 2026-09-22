import { createFileRoute } from "@tanstack/react-router";
import { buildGetSettingsQuery, buildGetVersionQuery } from "@/api/admin";
import { SettingsPage } from "@/components/settings/settings-page";
import { PrefectLoading } from "@/components/ui/loading";
import { usePageTitle } from "@/hooks/use-page-title";

export const Route = createFileRoute("/settings")({
	component: function RouteComponent() {
		usePageTitle("Settings");
		return <SettingsPage />;
	},
	loader: ({ context }) =>
		Promise.all([
			context.queryClient.ensureQueryData(buildGetSettingsQuery()),
			context.queryClient.ensureQueryData(buildGetVersionQuery()),
		]),
	wrapInSuspense: true,
	pendingComponent: PrefectLoading,
});
