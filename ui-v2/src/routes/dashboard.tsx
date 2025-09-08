import { createFileRoute } from "@tanstack/react-router";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
	LayoutWell,
	LayoutWellContent,
	LayoutWellHeader,
} from "@/components/ui/layout-well";
import { Skeleton } from "@/components/ui/skeleton";

export const Route = createFileRoute("/dashboard")({
	component: RouteComponent,
});

export function RouteComponent() {
	return (
		<LayoutWell>
			<LayoutWellContent>
				<LayoutWellHeader>
					<div className="flex flex-col space-y-4 md:space-y-0 md:flex-row md:items-center md:justify-between">
						<div>
							<Breadcrumb>
								<BreadcrumbList>
									<BreadcrumbItem className="text-2xl font-bold text-foreground">
										Dashboard
									</BreadcrumbItem>
								</BreadcrumbList>
							</Breadcrumb>
						</div>
						<div className="flex flex-col w-full max-w-full gap-2 md:w-auto md:inline-flex md:flex-row items-center">
							{/* Placeholder for future filter controls */}
							<div className="hidden md:flex items-center gap-2">
								<Skeleton className="h-9 w-32" /> {/* Hide subflows toggle */}
								<Skeleton className="h-9 w-40" /> {/* Tags filter */}
								<Skeleton className="h-9 w-48" /> {/* Date range selector */}
							</div>
						</div>
					</div>
				</LayoutWellHeader>

				<div className="grid grid-cols-1 gap-4 items-start xl:grid-cols-2">
					{/* Main content - Flow Runs Card */}
					<div className="space-y-4">
						<Card>
							<CardHeader>
								<CardTitle>Flow Runs</CardTitle>
							</CardHeader>
							<CardContent className="space-y-4">
								<div className="h-64 bg-muted rounded-md flex items-center justify-center">
									<span className="text-muted-foreground">
										Flow runs chart and table will appear here
									</span>
								</div>
							</CardContent>
						</Card>
					</div>

					{/* Sidebar - Task Runs and Work Pools Cards */}
					<div className="grid grid-cols-1 gap-4">
						<Card>
							<CardHeader>
								<CardTitle>Cumulative Task Runs</CardTitle>
							</CardHeader>
							<CardContent>
								<div className="h-48 bg-muted rounded-md flex items-center justify-center">
									<span className="text-muted-foreground">
										Cumulative task runs chart will appear here
									</span>
								</div>
							</CardContent>
						</Card>

						<Card>
							<CardHeader>
								<CardTitle>Work Pools</CardTitle>
							</CardHeader>
							<CardContent>
								<div className="h-48 bg-muted rounded-md flex items-center justify-center">
									<span className="text-muted-foreground">
										Work pools status will appear here
									</span>
								</div>
							</CardContent>
						</Card>
					</div>
				</div>
			</LayoutWellContent>
		</LayoutWell>
	);
}
