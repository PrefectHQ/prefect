import { Automation, useUpdateAutomation } from "@/api/automations";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/hooks/use-toast";

type AutomationEnableToggleProps = {
	automation: Automation;
};
export const AutomationEnableToggle = ({
	automation,
}: AutomationEnableToggleProps) => {
	const { toast } = useToast();

	const { updateAutomation } = useUpdateAutomation();

	const handleCheckedChange = (checked: boolean, id: string) => {
		updateAutomation(
			{
				enabled: checked,
				id,
			},
			{
				onSuccess: () => {
					toast({
						description: `Automation ${checked ? "enabled" : "disabled"}`,
					});
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
