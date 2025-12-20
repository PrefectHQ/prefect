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
		<div className="flex items-center justify-between">
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
			<FlowMenu flow={flow} onDelete={onDelete} />
		</div>
	);
}
