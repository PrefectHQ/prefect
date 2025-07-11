import { Link } from "@tanstack/react-router";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";

export const WorkPoolsPageHeader = () => (
	<div className="flex items-center gap-2">
		<Breadcrumb>
			<BreadcrumbList>
				<BreadcrumbItem className="text-xl font-semibold">
					Work pools
				</BreadcrumbItem>
			</BreadcrumbList>
		</Breadcrumb>
		<Link to="/work-pools/create">
			<Button size="icon" className="size-7" variant="outline">
				<Icon id="Plus" className="size-4" />
			</Button>
		</Link>
	</div>
);
