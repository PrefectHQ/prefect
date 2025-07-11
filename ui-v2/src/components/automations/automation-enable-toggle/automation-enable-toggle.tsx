import { toast } from "sonner";
import { type Automation, useUpdateAutomation } from "@/api/automations";
import { Switch } from "@/components/ui/switch";

type AutomationEnableToggleProps = {
	automation: Automation;
};
export const AutomationEnableToggle = ({
	automation,
}: AutomationEnableToggleProps) => {
	const { updateAutomation } = useUpdateAutomation();

	const handleCheckedChange = (checked: boolean, id: string) => {
		updateAutomation(
			{
				enabled: checked,
				id,
			},
			{
				onSuccess: () => {
					toast.success(`Automation ${checked ? "enabled" : "disabled"}`);
				},
				onError: (error) => {
					const message =
						error.message || "Unknown error while updating automation";
					console.error(message);
				},
			},
		);
	};

	return (
		<Switch
			aria-label="toggle automation"
			checked={automation.enabled}
			onCheckedChange={(checked) => handleCheckedChange(checked, automation.id)}
		/>
	);
};
