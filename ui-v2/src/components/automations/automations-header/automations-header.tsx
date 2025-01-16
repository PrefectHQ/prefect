import {
	Breadcrumb,
	BreadcrumbItem,
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
				<BreadcrumbItem className="text-xl font-semibold">
					Automations
				</BreadcrumbItem>
			</BreadcrumbList>
		</Breadcrumb>
		<Link to="/automations/create" aria-label="create automation">
			<Button
				size="icon"
				className="h-7 w-7"
				variant="outline"
				aria-label="create automation"
			>
				<Icon id="Plus" className="h-4 w-4" />
			</Button>
		</Link>
	</div>
);
