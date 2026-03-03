import type { Flow } from "@/api/flows";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { FlowMenu } from "./flow-menu";

type FlowPageHeaderProps = {
	flow: Flow;
	onDelete: () => void;
};

export function FlowPageHeader({ flow, onDelete }: FlowPageHeaderProps) {
	return (
		<header className="flex items-center justify-between">
			<Breadcrumb className="min-w-0">
				<BreadcrumbList className="flex-nowrap">
					<BreadcrumbItem>
						<BreadcrumbLink to="/flows" className="text-xl font-semibold">
							Flows
						</BreadcrumbLink>
					</BreadcrumbItem>
					<BreadcrumbSeparator />
					<BreadcrumbItem className="text-xl font-semibold min-w-0">
						<BreadcrumbPage className="truncate block" title={flow.name}>
							{flow.name}
						</BreadcrumbPage>
					</BreadcrumbItem>
				</BreadcrumbList>
			</Breadcrumb>
			<FlowMenu flow={flow} onDelete={onDelete} />
		</header>
	);
}
