import { type Automation } from "@/api/automations";
import { ActionDetails } from "@/components/automations/action-details";
import { AutomationEnableToggle } from "@/components/automations/automation-enable-toggle";
import { AutomationsActionsMenu } from "@/components/automations/automations-actions-menu";
import { useDeleteAutomationConfirmationDialog } from "@/components/automations/use-delete-automation-confirmation-dialog";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Card } from "@/components/ui/card";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { Typography } from "@/components/ui/typography";

type DisplayType = "page" | "item";

type AutomationDetailsProps = {
	data: Automation;
	displayType: DisplayType;
};

export const AutomationDetails = ({
	data,
	displayType,
}: AutomationDetailsProps) => {
	if (displayType === "item") {
		return (
			<Card className="p-4 pt-5">
				<AutomationDetailsContent data={data} displayType={displayType} />
			</Card>
		);
	}
	return <AutomationDetailsContent data={data} displayType={displayType} />;
};

const AutomationDetailsContent = ({
	data,
	displayType,
}: AutomationDetailsProps) => {
	const [dialogState, confirmDelete] = useDeleteAutomationConfirmationDialog();

	const handleDelete = () =>
		confirmDelete(data, { shouldNavigate: displayType === "page" });

	return (
		<>
			<div className="flex flex-col gap-4">
				<AutomationDetailsHeader
					displayType={displayType}
					data={data}
					onDelete={handleDelete}
				/>
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

type AutomationDetailsHeaderProps = {
	data: Automation;
	displayType: DisplayType;
	onDelete: () => void;
};

const AutomationDetailsHeader = ({
	data,
	onDelete,
	displayType,
}: AutomationDetailsHeaderProps) => {
	return (
		<div className="flex items-center justify-between">
			<NavHeader displayType={displayType} data={data} />
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

type NavHeaderProps = {
	data: Automation;
	displayType: DisplayType;
};

const NavHeader = ({ displayType, data }: NavHeaderProps) => {
	if (displayType === "page") {
		return (
			<div className="flex items-center gap-2">
				<Breadcrumb>
					<BreadcrumbList>
						<BreadcrumbItem>
							<BreadcrumbLink
								to="/automations"
								className="text-xl font-semibold"
							>
								Automations
							</BreadcrumbLink>
						</BreadcrumbItem>
						<BreadcrumbSeparator />
						<BreadcrumbItem className="text-xl font-semibold">
							<BreadcrumbPage>{data.name}</BreadcrumbPage>
						</BreadcrumbItem>
					</BreadcrumbList>
				</Breadcrumb>
			</div>
		);
	}

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
