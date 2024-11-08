import {
	Sidebar,
	SidebarContent,
	SidebarFooter,
	SidebarGroup,
	SidebarHeader,
	SidebarMenu,
	SidebarMenuItem,
	SidebarMenuButton,
} from "@/components/ui/sidebar";
import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";

const navItems = [
	{
		key: "dashboard",
		to: "/dashboard",
		display: <span>Dashboard</span>,
	},
	{
		key: "runs",
		to: "/runs",
		display: <span>Runs</span>,
	},
	{
		key: "flows",
		to: "/flows",
		display: <span>Flows</span>,
	},
	{
		key: "deployments",
		to: "/deployments",
		display: <span>Deployments</span>,
	},
	{
		key: "work-pools",
		to: "/work-pools",
		display: <span>Work Pools</span>,
	},
	{
		key: "blocks",
		to: "/blocks",
		display: <span>Blocks</span>,
	},
	{
		key: "variables",
		to: "/variables",
		display: <span>Variables</span>,
	},
	{
		key: "automations",
		to: "/automations",
		display: <span>Automations</span>,
	},
	{
		key: "event-feed",
		to: "/events",
		display: <span>Event Feed</span>,
	},
	{
		key: "notifications",
		to: "/notifications",
		display: <span>Notifications</span>,
	},
	{
		key: "concurrency-limits",
		to: "/concurrency-limits",
		display: <span>Concurrency</span>,
	},
] as const;

export function AppSidebar() {
	return (
		<Sidebar>
			<SidebarHeader>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					fill="none"
					viewBox="0 0 76 76"
					className="w-11 h-11"
					aria-label="Prefect Logo"
				>
					<title>Prefect Logo</title>
					<path
						fill="currentColor"
						fillRule="evenodd"
						d="M15.89 15.07 38 26.543v22.935l22.104-11.47.007.004V15.068l-.003.001L38 3.598z"
						clipRule="evenodd"
					/>
					<path
						fill="currentColor"
						fillRule="evenodd"
						d="M15.89 15.07 38 26.543v22.935l22.104-11.47.007.004V15.068l-.003.001L38 3.598z"
						clipRule="evenodd"
					/>
					<path
						fill="currentColor"
						fillRule="evenodd"
						d="M37.987 49.464 15.89 38v22.944l.013-.006L38 72.402V49.457z"
						clipRule="evenodd"
					/>
				</svg>
			</SidebarHeader>
			<SidebarContent>
				<SidebarGroup>
					<SidebarMenu>
						{navItems.map((item) => (
							<SidebarMenuItem key={item.key}>
								<Link to={item.to}>
									{({ isActive }) => (
										<SidebarMenuButton asChild isActive={isActive}>
											{item.display}
										</SidebarMenuButton>
									)}
								</Link>
							</SidebarMenuItem>
						))}
					</SidebarMenu>
				</SidebarGroup>
			</SidebarContent>
			<SidebarFooter>
				<SidebarMenu>
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
					<SidebarMenuItem>
						<Link to="/settings">
							{({ isActive }) => (
								<SidebarMenuButton asChild isActive={isActive}>
									<span>Settings</span>
								</SidebarMenuButton>
							)}
						</Link>
					</SidebarMenuItem>
				</SidebarMenu>
			</SidebarFooter>
		</Sidebar>
	);
}
