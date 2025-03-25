import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectLabel,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

const TEMPLATE_TRIGGERS = {
	"deployment-status": "Deployment status",
	"flow-run-state": "Flow run state",
	"work-pool-status": "Work pool status",
	"work-queue-status": "Work queue status",
	custom: "Custom",
} as const;

export type TemplateTriggers = keyof typeof TEMPLATE_TRIGGERS;

type AutomationsTriggerTemplateSelectProps = {
	onValueChange: (value: TemplateTriggers) => void;
	value?: TemplateTriggers;
};

export const AutomationsTriggerTemplateSelect = ({
	onValueChange,
	value,
}: AutomationsTriggerTemplateSelectProps) => {
	return (
		<div>
			<Label htmlFor="automations-trigger-template-select">
				Trigger Template
			</Label>
			<Select value={value} onValueChange={onValueChange}>
				<SelectTrigger id="automations-trigger-template-select">
					<SelectValue placeholder="Select template" />
				</SelectTrigger>
				<SelectContent>
					<SelectGroup>
						<SelectLabel>Trigger templates</SelectLabel>
						{Object.keys(TEMPLATE_TRIGGERS).map((key) => (
							<SelectItem key={key} value={key}>
								{TEMPLATE_TRIGGERS[key as TemplateTriggers]}
							</SelectItem>
						))}
					</SelectGroup>
				</SelectContent>
			</Select>
		</div>
	);
};
