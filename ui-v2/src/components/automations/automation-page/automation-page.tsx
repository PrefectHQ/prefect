import { Automation, buildGetAutomationQuery } from "@/api/automations";
import { ActionDetails } from "@/components/automations/action-details";
import { AutomationEnableToggle } from "@/components/automations/automation-enable-toggle";
import { AutomationsActionsMenu } from "@/components/automations/automations-actions-menu";
import { useDeleteAutomationConfirmationDialog } from "@/components/automations/use-delete-automation-confirmation-dialog";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { Typography } from "@/components/ui/typography";
import { useSuspenseQuery } from "@tanstack/react-query";
import { NavHeader } from "./nav-header";

type AutomationPageProps = {
	id: string;
};

export const AutomationPage = ({ id }: AutomationPageProps) => {
	const { data } = useSuspenseQuery(buildGetAutomationQuery(id));
	const [dialogState, confirmDelete] = useDeleteAutomationConfirmationDialog();

	const handleDelete = () => confirmDelete(data, { shouldNavigate: true });

	return (
		<>
			<div className="flex flex-col gap-4">
				<AutomationPageHeader data={data} onDelete={handleDelete} />
				<div className="flex flex-col gap-4">
					<AutomationDescription data={data} />
					<AutomationTrigger data={data} />
					<AutomationActions data={data} />
				</div>
			</div>
			<DeleteConfirmationDialog {...dialogState} />
		</>
	);
};

type AutomationPageHeaderProps = {
	data: Automation;
	onDelete: () => void;
};

const AutomationPageHeader = ({
	data,
	onDelete,
}: AutomationPageHeaderProps) => {
	return (
		<div className="flex items-center justify-between">
			<NavHeader name={data.name} />
			<div className="flex items-center gap-2">
				<AutomationEnableToggle data={data} />
				<AutomationsActionsMenu id={data.id} onDelete={onDelete} />
			</div>
		</div>
	);
};

type AutomationDescriptionProps = {
	data: Automation;
};

const AutomationDescription = ({ data }: AutomationDescriptionProps) => {
	return (
		<div className="flex flex-col gap-1">
			<Typography className="text-muted-foreground" variant="bodySmall">
				Description
			</Typography>
			<Typography className="text-muted-foreground">
				{data.description || "None"}
			</Typography>
		</div>
	);
};

type AutomationTriggerProps = {
	data: Automation;
};

const AutomationTrigger = ({ data }: AutomationTriggerProps) => {
	const { trigger } = data;
	return (
		<div className="flex flex-col gap-1">
			<Typography>Trigger</Typography>
			<Typography variant="bodySmall">
				TODO: {JSON.stringify(trigger)}
			</Typography>
		</div>
	);
};

type AutomationActionsProps = {
	data: Automation;
};

const AutomationActions = ({ data }: AutomationActionsProps) => {
	const { actions } = data;
	return (
		<div className="flex flex-col gap-1">
			<Typography>{`Action${actions.length > 1 ? "s" : ""}`}</Typography>
			<ul className="flex flex-col gap-2">
				{actions.map((action, i) => (
					<li key={i}>
						<ActionDetails action={action} />
					</li>
				))}
			</ul>
		</div>
	);
};
