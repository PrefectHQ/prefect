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
		component: (
			<Link to="/dashboard">
				{({ isActive }) => (
					<SidebarMenuButton asChild isActive={isActive}>
						<span>Dashboard</span>
					</SidebarMenuButton>
				)}
			</Link>
		),
	},
	{
		key: "runs",
		component: (
			<Link to="/runs">
				{({ isActive }) => (
					<SidebarMenuButton asChild isActive={isActive}>
						<span>Runs</span>
					</SidebarMenuButton>
				)}
			</Link>
		),
	},
	{
		key: "flows",
		component: (
			<Link to="/flows">
				{({ isActive }) => (
					<SidebarMenuButton asChild isActive={isActive}>
						<span>Flows</span>
					</SidebarMenuButton>
				)}
			</Link>
		),
	},
	{
		key: "deployments",
		component: (
			<Link to="/deployments">
				{({ isActive }) => (
					<SidebarMenuButton asChild isActive={isActive}>
						<span>Deployments</span>
					</SidebarMenuButton>
				)}
			</Link>
		),
	},
	{
		key: "work-pools",
		component: (
			<Link to="/work-pools">
				{({ isActive }) => (
					<SidebarMenuButton asChild isActive={isActive}>
						<span>Work Pools</span>
					</SidebarMenuButton>
				)}
			</Link>
		),
	},
	{
		key: "blocks",
		component: (
			<Link to="/blocks">
				{({ isActive }) => (
					<SidebarMenuButton asChild isActive={isActive}>
						<span>Blocks</span>
					</SidebarMenuButton>
				)}
			</Link>
		),
	},
	{
		key: "variables",
		component: (
			<Link to="/variables">
				{({ isActive }) => (
					<SidebarMenuButton asChild isActive={isActive}>
						<span>Variables</span>
					</SidebarMenuButton>
				)}
			</Link>
		),
	},
	{
		key: "automations",
		component: (
			<Link to="/automations">
				{({ isActive }) => (
					<SidebarMenuButton asChild isActive={isActive}>
						<span>Automations</span>
					</SidebarMenuButton>
				)}
			</Link>
		),
	},
	{
		key: "event-feed",
		component: (
			<Link to="/events">
				{({ isActive }) => (
					<SidebarMenuButton asChild isActive={isActive}>
						<span>Event Feed</span>
					</SidebarMenuButton>
				)}
			</Link>
		),
	},
	{
		key: "notifications",
		component: (
			<Link to="/notifications">
				{({ isActive }) => (
					<SidebarMenuButton asChild isActive={isActive}>
						<span>Notifications</span>
					</SidebarMenuButton>
				)}
			</Link>
		),
	},
	{
		key: "concurrency-limits",
		component: (
			<Link to="/concurrency-limits">
				{({ isActive }) => (
					<SidebarMenuButton asChild isActive={isActive}>
						<span>Concurrency</span>
					</SidebarMenuButton>
				)}
			</Link>
		),
	},
] as const;

const footerItems = [
	{
		key: "upgrade",
		component: (
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
		),
	},
	{
		key: "community",
		component: (
			<SidebarMenuButton asChild>
				<span>Join the community</span>
			</SidebarMenuButton>
		),
	},
	{
		key: "settings",
		component: (
			<Link to="/settings">
				{({ isActive }) => (
					<SidebarMenuButton asChild isActive={isActive}>
						<span>Settings</span>
					</SidebarMenuButton>
				)}
			</Link>
		),
	},
];

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
							<SidebarMenuItem key={item.key}>{item.component}</SidebarMenuItem>
						))}
					</SidebarMenu>
				</SidebarGroup>
			</SidebarContent>
			<SidebarFooter>
				<SidebarMenu>
					{footerItems.map((item) => (
						<SidebarMenuItem key={item.key}>{item.component}</SidebarMenuItem>
					))}
				</SidebarMenu>
			</SidebarFooter>
		</Sidebar>
	);
}
