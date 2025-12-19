import type { Flow } from "@/api/flows";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

type FlowPageHeaderProps = {
	flow: Flow;
};

export function FlowPageHeader({ flow }: FlowPageHeaderProps) {
	return (
		<Breadcrumb>
			<BreadcrumbList>
				<BreadcrumbItem>
					<BreadcrumbLink to="/flows" className="text-xl font-semibold">
						Flows
					</BreadcrumbLink>
				</BreadcrumbItem>
				<BreadcrumbSeparator />
				<BreadcrumbItem className="text-xl font-semibold">
					<BreadcrumbPage>{flow.name}</BreadcrumbPage>
				</BreadcrumbItem>
			</BreadcrumbList>
		</Breadcrumb>
	);
}
