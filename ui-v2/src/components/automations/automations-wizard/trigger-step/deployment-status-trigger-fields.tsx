import { useFormContext, useWatch } from "react-hook-form";
import type { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import {
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { PostureSelect } from "./posture-select";

const DEPLOYMENT_STATUSES = [
	{ value: "prefect.deployment.ready", label: "Ready" },
	{ value: "prefect.deployment.not-ready", label: "Not Ready" },
];

export const DeploymentStatusTriggerFields = () => {
	const form = useFormContext<AutomationWizardSchema>();
	const posture = useWatch<AutomationWizardSchema>({ name: "trigger.posture" });

	return (
		<div className="space-y-4">
			<div className="flex items-end gap-4">
				<PostureSelect />
				<FormField
					control={form.control}
					name="trigger.expect"
					render={({ field }) => {
						const selectedStatus = field.value?.[0];
						return (
							<FormItem className="flex-1">
								<FormLabel>Status</FormLabel>
								<FormControl>
									<Select
										value={selectedStatus ?? ""}
										onValueChange={(value) => field.onChange([value])}
									>
										<SelectTrigger>
											<SelectValue placeholder="Select status" />
										</SelectTrigger>
										<SelectContent>
											{DEPLOYMENT_STATUSES.map((status) => (
												<SelectItem key={status.value} value={status.value}>
													{status.label}
												</SelectItem>
											))}
										</SelectContent>
									</Select>
								</FormControl>
								<FormMessage />
							</FormItem>
						);
					}}
				/>
			</div>

			<div className="flex gap-4">
				<FormField
					control={form.control}
					name="trigger.threshold"
					render={({ field }) => (
						<FormItem className="w-32">
							<FormLabel>Threshold</FormLabel>
							<FormControl>
								<Input
									type="number"
									min={1}
									{...field}
									onChange={(e) => field.onChange(Number(e.target.value))}
								/>
							</FormControl>
							<FormMessage />
						</FormItem>
					)}
				/>

				{posture === "Proactive" && (
					<FormField
						control={form.control}
						name="trigger.within"
						render={({ field }) => (
							<FormItem className="w-32">
								<FormLabel>Within (seconds)</FormLabel>
								<FormControl>
									<Input
										type="number"
										min={0}
										{...field}
										onChange={(e) => field.onChange(Number(e.target.value))}
									/>
								</FormControl>
								<FormMessage />
							</FormItem>
						)}
					/>
				)}
			</div>
		</div>
	);
};
