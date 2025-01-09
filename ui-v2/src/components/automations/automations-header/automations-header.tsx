import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { DocsLink } from "@/components/ui/docs-link";
import { Icon } from "@/components/ui/icons";
import { Link } from "@tanstack/react-router";

export const AutomationsHeader = () => {
	return (
		<div className="flex items-center justify-between">
			<Header />
			<DocsLink id="automations-guide" label="Documentation" />
		</div>
	);
};

const Header = () => (
	<div className="flex items-center gap-2">
		<Breadcrumb>
			<BreadcrumbList>
				<BreadcrumbItem>
					<BreadcrumbLink
						to="/concurrency-limits"
						className="text-xl font-semibold"
					>
						Automations
					</BreadcrumbLink>
				</BreadcrumbItem>
			</BreadcrumbList>
		</Breadcrumb>
		<Button size="icon" className="h-7 w-7" variant="outline">
			<Link to="/automations/create">
				<Icon id="Plus" className="h-4 w-4" />
			</Link>
		</Button>
	</div>
);
