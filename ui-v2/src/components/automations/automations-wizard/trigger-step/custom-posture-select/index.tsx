import { useFormContext } from "react-hook-form";
import type { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import {
	FormControl,
	FormField,
	FormItem,
	FormLabel,
} from "@/components/ui/form";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";

const POSTURE_OPTIONS = [
	{ value: "Reactive", label: "Observe" },
	{ value: "Proactive", label: "Don't observe" },
] as const;

const DEFAULT_PROACTIVE_WITHIN = 30;

export const CustomPostureSelect = () => {
	const form = useFormContext<AutomationWizardSchema>();

	const handlePostureChange = (value: "Reactive" | "Proactive") => {
		const previousPosture = form.getValues("trigger.posture");
		form.setValue("trigger.posture", value);

		// Move state values between expect and after when posture changes
		// Reactive uses "expect", Proactive uses "after"
		if (previousPosture === "Reactive" && value === "Proactive") {
			const expectValues = form.getValues("trigger.expect") ?? [];
			form.setValue("trigger.after", expectValues);
			form.setValue("trigger.expect", []);
			const currentWithin = form.getValues("trigger.within");
			if (currentWithin === 0) {
				form.setValue("trigger.within", DEFAULT_PROACTIVE_WITHIN);
			}
		} else if (previousPosture === "Proactive" && value === "Reactive") {
			const afterValues = form.getValues("trigger.after") ?? [];
			form.setValue("trigger.expect", afterValues);
			form.setValue("trigger.after", []);
		}
	};

	return (
		<FormField
			control={form.control}
			name="trigger.posture"
			render={({ field }) => (
				<FormItem>
					<FormLabel>When I</FormLabel>
					<FormControl>
						<RadioGroup
							value={field.value}
							onValueChange={handlePostureChange}
							className="flex gap-4"
						>
							{POSTURE_OPTIONS.map((option) => (
								<div key={option.value} className="flex items-center gap-2">
									<RadioGroupItem
										value={option.value}
										id={`custom-${option.value}`}
									/>
									<Label htmlFor={`custom-${option.value}`}>
										{option.label}
									</Label>
								</div>
							))}
						</RadioGroup>
					</FormControl>
				</FormItem>
			)}
		/>
	);
};
