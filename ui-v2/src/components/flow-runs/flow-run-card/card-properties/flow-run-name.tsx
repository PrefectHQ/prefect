import type { FlowRunCardData } from "@/components/flow-runs/flow-run-card";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Icon } from "@/components/ui/icons";

type FlowRunNameProps = {
	flowRun: FlowRunCardData;
};

export const FlowRunName = ({ flowRun }: FlowRunNameProps) => {
	const { flow } = flowRun;

	return (
		<div className="flex items-center">
			<Breadcrumb>
				<BreadcrumbList>
					{flow && (
						<BreadcrumbItem>
							<BreadcrumbLink
								to="/flows/flow/$id"
								params={{ id: flowRun.flow_id }}
								className="flex items-center gap-1"
							>
								<Icon id="Workflow" className="size-4" />
								{flow.name}
							</BreadcrumbLink>
						</BreadcrumbItem>
					)}
					{flow && <BreadcrumbSeparator>/</BreadcrumbSeparator>}
					<BreadcrumbItem className="font-bold text-foreground">
						<BreadcrumbLink to="/runs/flow-run/$id" params={{ id: flowRun.id }}>
							{flowRun.name}
						</BreadcrumbLink>
					</BreadcrumbItem>
				</BreadcrumbList>
			</Breadcrumb>
		</div>
	);
};
