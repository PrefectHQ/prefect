import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { DocsLink } from "@/components/ui/docs-link";

export const AutomationsCreateHeader = () => (
	<div className="flex items-center justify-between">
		<NavHeader />
		<DocsLink label="Documentation" id="automations-guide" />
	</div>
);

const NavHeader = () => (
	<div className="flex items-center gap-2">
		<Breadcrumb>
			<BreadcrumbList>
				<BreadcrumbItem>
					<BreadcrumbLink to="/automations" className="text-xl font-semibold">
						Automations
					</BreadcrumbLink>
				</BreadcrumbItem>
				<BreadcrumbSeparator />
				<BreadcrumbItem className="text-xl font-semibold">
					<BreadcrumbPage>Create</BreadcrumbPage>
				</BreadcrumbItem>
			</BreadcrumbList>
		</Breadcrumb>
	</div>
);
