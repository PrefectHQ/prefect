import { useSuspenseQuery } from "@tanstack/react-query";
import { type Automation, buildListAutomationsQuery } from "@/api/automations";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
} from "@/components/ui/breadcrumb";
import { Card } from "@/components/ui/card";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { Typography } from "../ui/typography";
import {
	AutomationActions,
	AutomationDescription,
	AutomationTrigger,
} from "./automation-details";
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
					<div className="flex flex-col gap-4">
						<Typography variant="bodySmall" className="text-muted-foreground">
							{data.length}{" "}
							{`${data.length === 1 ? "automation" : "automations"}`}
						</Typography>
						<ul className="flex flex-col gap-2">
							{data.map((automation) => (
								<li
									key={automation.id}
									aria-label={`automation item ${automation.name}`}
								>
									<AutomationCardDetails
										automation={automation}
										onDelete={() => handleDelete(automation)}
									/>
								</li>
							))}
						</ul>
					</div>
				)}
			</div>
			<DeleteConfirmationDialog {...dialogState} />
		</>
	);
};

type AutomationCardDetailsProps = {
	automation: Automation;
	onDelete: () => void;
};
const AutomationCardDetails = ({
	automation,
	onDelete,
}: AutomationCardDetailsProps) => {
	return (
		<Card className="p-4 pt-5 flex flex-col gap-6">
			<div className="flex items-center justify-between">
				<NavHeader automation={automation} />
				<div className="flex items-center gap-2">
					<AutomationEnableToggle automation={automation} />
					<AutomationsActionsMenu id={automation.id} onDelete={onDelete} />
				</div>
			</div>
			<div className="flex flex-col gap-4">
				{automation.description && (
					<AutomationDescription automation={automation} />
				)}
				<AutomationTrigger automation={automation} />
				<AutomationActions automation={automation} />
			</div>
		</Card>
	);
};

type NavHeaderProps = {
	automation: Automation;
};

const NavHeader = ({ automation }: NavHeaderProps) => {
	return (
		<Breadcrumb>
			<BreadcrumbList>
				<BreadcrumbItem className="text-xl">
					<BreadcrumbLink
						to="/automations/automation/$id"
						params={{ id: automation.id }}
						className="text-lg"
					>
						{automation.name}
					</BreadcrumbLink>
				</BreadcrumbItem>
			</BreadcrumbList>
		</Breadcrumb>
	);
};
