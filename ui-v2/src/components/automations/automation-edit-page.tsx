import { AutomationsCreateHeader } from "./automations-create-header";
import { AutomationEditWizard } from "./automations-wizard/automation-edit-wizard";

type AutomationEditPageProps = {
	id: string;
};

export const AutomationEditPage = ({ id }: AutomationEditPageProps) => {
	return (
		<div className="flex flex-col gap-4">
			<AutomationsCreateHeader
				breadcrumbs={[
					{ label: "Automations", href: "/automations" },
					{ label: "Edit Automation" },
				]}
			/>
			<AutomationEditWizard automationId={id} />
		</div>
	);
};
