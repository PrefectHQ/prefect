import type { Automation } from "@/api/automations";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { DocsLink } from "@/components/ui/docs-link";

type AutomationsEditHeaderProps = {
	automation: Automation;
};

export const AutomationsEditHeader = ({
	automation,
}: AutomationsEditHeaderProps) => (
	<div className="flex items-center justify-between">
		<NavHeader automation={automation} />
		<DocsLink label="Documentation" id="automations-guide" />
	</div>
);

type NavHeaderProps = {
	automation: Automation;
};

const NavHeader = ({ automation }: NavHeaderProps) => (
	<Breadcrumb className="min-w-0">
		<BreadcrumbList className="flex-nowrap">
			<BreadcrumbItem>
				<BreadcrumbLink to="/automations" className="text-xl font-semibold">
					Automations
				</BreadcrumbLink>
			</BreadcrumbItem>
			<BreadcrumbSeparator />
			<BreadcrumbItem className="min-w-0">
				<BreadcrumbLink
					to="/automations/automation/$id"
					params={{ id: automation.id }}
					className="text-xl font-semibold truncate block"
					title={automation.name}
				>
					{automation.name}
				</BreadcrumbLink>
			</BreadcrumbItem>
			<BreadcrumbSeparator />
			<BreadcrumbItem className="text-xl font-semibold">
				<BreadcrumbPage>Edit</BreadcrumbPage>
			</BreadcrumbItem>
		</BreadcrumbList>
	</Breadcrumb>
);
