import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
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

export function AppSidebar() {
	return (
		<Sidebar>
			<SidebarHeader>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					fill="none"
					viewBox="0 0 76 76"
					className="size-11"
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
