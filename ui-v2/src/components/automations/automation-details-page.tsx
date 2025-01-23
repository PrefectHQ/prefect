import { type Automation, buildGetAutomationQuery } from "@/api/automations";
import {
	Breadcrumb,
	BreadcrumbItem,
	BreadcrumbLink,
	BreadcrumbList,
	BreadcrumbPage,
	BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { useSuspenseQuery } from "@tanstack/react-query";
import { AutomationDetails } from "./automation-details";
import { AutomationEnableToggle } from "./automation-enable-toggle";
import { AutomationsActionsMenu } from "./automations-actions-menu";

import { useDeleteAutomationConfirmationDialog } from "./use-delete-automation-confirmation-dialog";

type AutomationsDetailsPageProps = {
	id: string;
};

export const AutomationDetailsPage = ({ id }: AutomationsDetailsPageProps) => {
	const [dialogState, confirmDelete] = useDeleteAutomationConfirmationDialog();
	const { data } = useSuspenseQuery(buildGetAutomationQuery(id));

	const handleDelete = () => confirmDelete(data, { shouldNavigate: true });

	return (
		<>
			<div className="flex flex-col gap-6">
				<div className="flex items-center justify-between">
					<NavHeader data={data} />
					<div className="flex items-center gap-2">
						<AutomationEnableToggle data={data} />
						<AutomationsActionsMenu id={data.id} onDelete={handleDelete} />
					</div>
				</div>
				<AutomationDetails data={data} />
			</div>
			<DeleteConfirmationDialog {...dialogState} />
		</>
	);
};

type NavHeaderProps = {
	data: Automation;
};
const NavHeader = ({ data }: NavHeaderProps) => {
	return (
		<Breadcrumb>
			<BreadcrumbList>
				<BreadcrumbItem>
					<BreadcrumbLink to="/automations" className="text-xl font-semibold">
						Automations
					</BreadcrumbLink>
				</BreadcrumbItem>
				<BreadcrumbSeparator />
				<BreadcrumbItem className="text-xl font-semibold">
					<BreadcrumbPage>{data.name}</BreadcrumbPage>
				</BreadcrumbItem>
			</BreadcrumbList>
		</Breadcrumb>
	);
};
