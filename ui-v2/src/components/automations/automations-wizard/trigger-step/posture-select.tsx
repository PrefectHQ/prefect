import { useFormContext } from "react-hook-form";
import type { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { FormControl, FormField, FormItem } from "@/components/ui/form";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

const POSTURE_OPTIONS = [
	{ value: "Reactive", label: "Enters" },
	{ value: "Proactive", label: "Stays in" },
] as const;

const DEFAULT_PROACTIVE_WITHIN = 30;

export const PostureSelect = () => {
	const form = useFormContext<AutomationWizardSchema>();

	return (
		<FormField
			control={form.control}
			name="trigger.posture"
			render={({ field }) => (
				<FormItem>
					<FormControl>
						<Select
							value={field.value}
							onValueChange={(value: "Reactive" | "Proactive") => {
								const previousPosture = field.value;
								field.onChange(value);

								// Move state values between expect and after when posture changes
								// Reactive uses "expect", Proactive uses "after"
								if (previousPosture === "Reactive" && value === "Proactive") {
									// Moving from Reactive to Proactive: move expect to after
									const expectValues = form.getValues("trigger.expect") ?? [];
									form.setValue("trigger.after", expectValues);
									form.setValue("trigger.expect", []);
									// Set a default within value if it's 0
									const currentWithin = form.getValues("trigger.within");
									if (currentWithin === 0) {
										form.setValue("trigger.within", DEFAULT_PROACTIVE_WITHIN);
									}
								} else if (
									previousPosture === "Proactive" &&
									value === "Reactive"
								) {
									// Moving from Proactive to Reactive: move after to expect
									const afterValues = form.getValues("trigger.after") ?? [];
									form.setValue("trigger.expect", afterValues);
									form.setValue("trigger.after", []);
								}
							}}
						>
							<SelectTrigger aria-label="select posture" className="w-[160px]">
								<SelectValue placeholder="Select posture" />
							</SelectTrigger>
							<SelectContent>
								{POSTURE_OPTIONS.map((option) => (
									<SelectItem key={option.value} value={option.value}>
										{option.label}
									</SelectItem>
								))}
							</SelectContent>
						</Select>
					</FormControl>
				</FormItem>
			)}
		/>
	);
};
