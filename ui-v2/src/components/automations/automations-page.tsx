import { type Automation, buildListAutomationsQuery } from "@/api/automations";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";
import { Card } from "@/components/ui/card";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { useSuspenseQuery } from "@tanstack/react-query";

import { AutomationDetails } from "./automation-details";
import { AutomationEnableToggle } from "./automation-enable-toggle";
import { AutomationsActionsMenu } from "./automations-actions-menu";
import { AutomationsEmptyState } from "./automations-empty-state";
import { AutomationsHeader } from "./automations-header";
import { useDeleteAutomationConfirmationDialog } from "./use-delete-automation-confirmation-dialog";

export const AutomationsPage = () => {
	const [dialogState, confirmDelete] = useDeleteAutomationConfirmationDialog();
	const { data } = useSuspenseQuery(buildListAutomationsQuery());

	const handleDelete = (automation: Automation) => confirmDelete(automation);

	return (
		<>
			<div className="flex flex-col gap-4">
				<AutomationsHeader />
				{data.length === 0 ? (
					<AutomationsEmptyState />
				) : (
					<ul className="flex flex-col gap-2">
						{data.map((automation) => (
							<li
								key={automation.id}
								aria-label={`automation item ${automation.name}`}
							>
								<AutomationCardDetails
									data={automation}
									onDelete={() => handleDelete(automation)}
								/>
							</li>
						))}
					</ul>
				)}
			</div>
			<DeleteConfirmationDialog {...dialogState} />
		</>
	);
};

type AutomationCardDetailsProps = {
	data: Automation;
	onDelete: () => void;
};
const AutomationCardDetails = ({
	data,
	onDelete,
}: AutomationCardDetailsProps) => {
	return (
		<Card className="p-4 pt-5 flex flex-col gap-6">
			<div className="flex items-center justify-between">
				<NavHeader data={data} />
				<div className="flex items-center gap-2">
					<AutomationEnableToggle data={data} />
					<AutomationsActionsMenu id={data.id} onDelete={onDelete} />
				</div>
			</div>
			<AutomationDetails data={data} />
		</Card>
	);
};

type NavHeaderProps = {
	data: Automation;
};

const NavHeader = ({ data }: NavHeaderProps) => {
	return (
		<Breadcrumb>
			<BreadcrumbList>
				<BreadcrumbItem className="text-xl">
					<BreadcrumbLink
						to="/automations/automation/$id"
						params={{ id: data.id }}
						className="text-lg"
					>
						{data.name}
					</BreadcrumbLink>
				</BreadcrumbItem>
			</BreadcrumbList>
		</Breadcrumb>
	);
};
