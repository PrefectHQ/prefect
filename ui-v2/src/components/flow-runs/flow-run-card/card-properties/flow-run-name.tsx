import type { FlowRunCardData } from "@/components/flow-runs/flow-run-card";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

type FlowRunNameProps = {
	flowRun: FlowRunCardData;
};

export const FlowRunName = ({ flowRun }: FlowRunNameProps) => {
	const { flow } = flowRun;

	return (
		<div className="flex items-center min-w-0 overflow-hidden">
			<Breadcrumb className="min-w-0">
				<BreadcrumbList className="flex-nowrap min-w-0 overflow-hidden">
					{flow && (
						<BreadcrumbItem className="min-w-0">
							<BreadcrumbLink
								to="/flows/flow/$id"
								params={{ id: flowRun.flow_id }}
								className="truncate block"
								title={flow.name}
							>
								{flow.name}
							</BreadcrumbLink>
						</BreadcrumbItem>
					)}
					{flow && <BreadcrumbSeparator>/</BreadcrumbSeparator>}
					<BreadcrumbItem className="font-bold text-foreground min-w-0">
						<BreadcrumbLink
							to="/runs/flow-run/$id"
							params={{ id: flowRun.id }}
							className="truncate block"
							title={flowRun.name}
						>
							{flowRun.name}
						</BreadcrumbLink>
					</BreadcrumbItem>
				</BreadcrumbList>
			</Breadcrumb>
		</div>
	);
};
