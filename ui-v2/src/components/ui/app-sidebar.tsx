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

const items = [
	{
		title: "Dashboard",
		url: "/dashboard",
	},
	{
		title: "Runs",
		url: "/runs",
	},
	{
		title: "Flows",
		url: "/flows",
	},
	{
		title: "Deployments",
		url: "/deployments",
	},
	{
		title: "Work Pools",
		url: "/work-pools",
	},
	{
		title: "Blocks",
		url: "/blocks",
	},
	{
		title: "Variables",
		url: "/variables",
	},
	{
		title: "Automations",
		url: "/automations",
	},
	{
		title: "Event Feed",
		url: "/events",
	},
	{
		title: "Notifications",
		url: "/notifications",
	},
	{
		title: "Concurrency",
		url: "/concurrency-limits",
	},
];

export function AppSidebar() {
	return (
		<Sidebar>
			<SidebarHeader>Prefect</SidebarHeader>
			<SidebarContent>
				<SidebarGroup>
					<SidebarMenu>
						{items.map((item) => (
							<SidebarMenuItem key={item.title}>
								<Link to={item.url}>
									{({ isActive }) => (
										<SidebarMenuButton asChild isActive={isActive}>
											<span>{item.title}</span>
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
						<SidebarMenuButton asChild>
							<span>Ready to scale?</span>
						</SidebarMenuButton>
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
