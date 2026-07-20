import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { LogOut } from "lucide-react";
import { useState } from "react";
import { buildGetSettingsQuery } from "@/api/admin";
import { buildUiSettingsQuery } from "@/api/ui-settings";
import { useAuthSafe } from "@/auth";
import { Button } from "@/components/ui/button";
import { PrefectLogo } from "@/components/ui/prefect-logo";
import {
	Sidebar,
	SidebarContent,
	SidebarFooter,
	SidebarGroup,
	SidebarHeader,
	SidebarMenu,
	SidebarMenuButton,
	SidebarMenuItem,
} from "@/components/ui/sidebar";
import {
	switchToV1Ui,
	UiVersionSwitchDialog,
	type UiVersionSwitchDialogValues,
} from "@/components/ui-version-switch";
import { isUiAvailable } from "@/utils/ui-version";

export function AppSidebar() {
	const auth = useAuthSafe();
	const navigate = useNavigate();
	const [isSwitchDialogOpen, setIsSwitchDialogOpen] = useState(false);

	const handleLogout = () => {
		auth?.logout();
		void navigate({ to: "/login" });
	};

	const authRequired = auth?.authRequired ?? false;

	const { data: settings } = useQuery(buildGetSettingsQuery());
	const { data: browserUiSettings } = useQuery(buildUiSettingsQuery());
	const showPromotionalContent = (() => {
		const server = (settings as Record<string, unknown> | undefined)?.server as
			| Record<string, unknown>
			| undefined;
		const ui = server?.ui as Record<string, unknown> | undefined;
		return (ui?.show_promotional_content as boolean | undefined) ?? true;
	})();
	const analyticsEnabled = (() => {
		const server = (settings as Record<string, unknown> | undefined)?.server as
			| Record<string, unknown>
			| undefined;
		return (server?.analytics_enabled as boolean | undefined) ?? false;
	})();
	const canSwitchToV1 =
		isUiAvailable(browserUiSettings?.availableUis, "v1") &&
		Boolean(browserUiSettings?.v1BaseUrl);

	const handleSwitchToV1 = (feedback?: UiVersionSwitchDialogValues) => {
		if (!browserUiSettings) {
			return;
		}

		switchToV1Ui({
			uiSettings: browserUiSettings,
			analyticsEnabled,
			feedback,
		});
	};

	return (
		<Sidebar>
			<SidebarHeader>
				<PrefectLogo />
			</SidebarHeader>
			<SidebarContent>
				<SidebarGroup>
					<SidebarMenu>
						<SidebarMenuItem>
							<Link to="/dashboard">
								{({ isActive }) => (
									<SidebarMenuButton asChild isActive={isActive}>
										<span>Dashboard</span>
									</SidebarMenuButton>
								)}
							</Link>
						</SidebarMenuItem>
						<SidebarMenuItem>
							<Link to="/runs">
								{({ isActive }) => (
									<SidebarMenuButton asChild isActive={isActive}>
										<span>Runs</span>
									</SidebarMenuButton>
								)}
							</Link>
						</SidebarMenuItem>
						<SidebarMenuItem>
							<Link to="/flows">
								{({ isActive }) => (
									<SidebarMenuButton asChild isActive={isActive}>
										<span>Flows</span>
									</SidebarMenuButton>
								)}
							</Link>
						</SidebarMenuItem>
						<SidebarMenuItem>
							<Link to="/deployments">
								{({ isActive }) => (
									<SidebarMenuButton asChild isActive={isActive}>
										<span>Deployments</span>
									</SidebarMenuButton>
								)}
							</Link>
						</SidebarMenuItem>
						<SidebarMenuItem>
							<Link to="/work-pools">
								{({ isActive }) => (
									<SidebarMenuButton asChild isActive={isActive}>
										<span>Work Pools</span>
									</SidebarMenuButton>
								)}
							</Link>
						</SidebarMenuItem>
						<SidebarMenuItem>
							<Link to="/blocks">
								{({ isActive }) => (
									<SidebarMenuButton asChild isActive={isActive}>
										<span>Blocks</span>
									</SidebarMenuButton>
								)}
							</Link>
						</SidebarMenuItem>
						<SidebarMenuItem>
							<Link to="/variables">
								{({ isActive }) => (
									<SidebarMenuButton asChild isActive={isActive}>
										<span>Variables</span>
									</SidebarMenuButton>
								)}
							</Link>
						</SidebarMenuItem>
						<SidebarMenuItem>
							<Link to="/automations">
								{({ isActive }) => (
									<SidebarMenuButton asChild isActive={isActive}>
										<span>Automations</span>
									</SidebarMenuButton>
								)}
							</Link>
						</SidebarMenuItem>
						<SidebarMenuItem>
							<Link to="/events">
								{({ isActive }) => (
									<SidebarMenuButton asChild isActive={isActive}>
										<span>Event Feed</span>
									</SidebarMenuButton>
								)}
							</Link>
						</SidebarMenuItem>
						<SidebarMenuItem>
							<Link to="/concurrency-limits">
								{({ isActive }) => (
									<SidebarMenuButton asChild isActive={isActive}>
										<span>Concurrency</span>
									</SidebarMenuButton>
								)}
							</Link>
						</SidebarMenuItem>
					</SidebarMenu>
				</SidebarGroup>
			</SidebarContent>
			<SidebarFooter>
				<SidebarMenu>
					{showPromotionalContent && (
						<>
							<SidebarMenuItem>
								<a
									href="https://prefect.io/cloud-vs-oss?utm_source=oss&utm_medium=oss&utm_campaign=oss&utm_term=none&utm_content=none"
									target="_blank"
									rel="noreferrer"
								>
									<SidebarMenuButton asChild>
										<div className="flex items-center justify-between">
											<span>Ready to scale?</span>
											<Button size="sm">Upgrade</Button>
										</div>
									</SidebarMenuButton>
								</a>
							</SidebarMenuItem>
							<SidebarMenuItem>
								<SidebarMenuButton asChild>
									<span>Join the community</span>
								</SidebarMenuButton>
							</SidebarMenuItem>
						</>
					)}
					<SidebarMenuItem>
						<Link to="/settings">
							{({ isActive }) => (
								<SidebarMenuButton asChild isActive={isActive}>
									<span>Settings</span>
								</SidebarMenuButton>
							)}
						</Link>
					</SidebarMenuItem>
					{canSwitchToV1 && (
						<SidebarMenuItem>
							<SidebarMenuButton onClick={() => setIsSwitchDialogOpen(true)}>
								<span>Switch to V1 UI</span>
							</SidebarMenuButton>
						</SidebarMenuItem>
					)}
					{authRequired && (
						<SidebarMenuItem>
							<SidebarMenuButton onClick={handleLogout}>
								<LogOut className="h-4 w-4" />
								<span>Logout</span>
							</SidebarMenuButton>
						</SidebarMenuItem>
					)}
				</SidebarMenu>
			</SidebarFooter>
			<UiVersionSwitchDialog
				open={isSwitchDialogOpen}
				onOpenChange={setIsSwitchDialogOpen}
				onSkipFeedback={() => handleSwitchToV1()}
				onSubmitFeedback={(values) => handleSwitchToV1(values)}
			/>
		</Sidebar>
	);
}
