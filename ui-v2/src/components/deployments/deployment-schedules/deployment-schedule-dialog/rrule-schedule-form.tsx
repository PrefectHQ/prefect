import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import {
	useCreateDeploymentSchedule,
	useUpdateDeploymentSchedule,
} from "@/api/deployments";
import { Button } from "@/components/ui/button";
import { DialogClose, DialogFooter } from "@/components/ui/dialog";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import {
	parseRule,
	RRuleBuilder,
	serializeRule,
} from "@/components/ui/rrule-builder";
import { Switch } from "@/components/ui/switch";
import { TimezoneSelect } from "@/components/ui/timezone-select";
import type { CronScheduleFormProps } from "./cron-schedule-form";
import { ScheduleParameterOverridesFormSection } from "./schedule-parameter-overrides-form-section";

const schema = z.object({
	active: z.boolean(),
	schedule: z.object({ rrule: z.string(), timezone: z.string() }),
});

export function RRuleScheduleForm({
	deployment_id,
	scheduleToEdit,
	onSubmit,
	parameterOverrides,
}: CronScheduleFormProps) {
	const [defaults] = useState(() => {
		const start = new Date().toISOString().slice(0, 10).replaceAll("-", "");
		return {
			active: scheduleToEdit?.active ?? true,
			schedule:
				scheduleToEdit && "rrule" in scheduleToEdit.schedule
					? {
							rrule: scheduleToEdit.schedule.rrule,
							timezone: scheduleToEdit.schedule.timezone ?? "UTC",
						}
					: {
							rrule: `DTSTART;TZID=UTC:${start}T090000\nRRULE:FREQ=DAILY`,
							timezone: "UTC",
						},
		};
	});
	const [readOnly] = useState(
		() =>
			!parseRule(defaults.schedule.rrule, defaults.schedule.timezone).supported,
	);
	const [valid, setValid] = useState(true);
	const form = useForm({
		defaultValues: defaults,
		resolver: zodResolver(schema),
	});
	const schedule = form.watch("schedule");
	const { createDeploymentSchedule, isPending: creating } =
		useCreateDeploymentSchedule();
	const { updateDeploymentSchedule, isPending: updating } =
		useUpdateDeploymentSchedule();
	const save = async (values: z.infer<typeof schema>) => {
		if (
			(!readOnly &&
				(!valid ||
					!parseRule(values.schedule.rrule, values.schedule.timezone)
						.supported)) ||
			(parameterOverrides && !(await parameterOverrides.validate()))
		)
			return;
		const parsed = parseRule(values.schedule.rrule, values.schedule.timezone);
		const body = {
			deployment_id,
			active: values.active,
			parameters: parameterOverrides?.values,
			...(!readOnly && parsed.supported
				? {
						schedule: {
							rrule: serializeRule(parsed.value, values.schedule.timezone),
							timezone: values.schedule.timezone,
						},
					}
				: {}),
		};
		const callbacks = {
			onSuccess: () => {
				toast.success(
					`Deployment schedule ${scheduleToEdit ? "updated" : "created"}`,
				);
				onSubmit();
			},
			onError: (error: Error) =>
				form.setError("root", {
					message: error.message || "Unable to save deployment schedule.",
				}),
		};
		if (scheduleToEdit)
			updateDeploymentSchedule(
				{ ...body, schedule_id: scheduleToEdit.id },
				callbacks,
			);
		else if (body.schedule)
			createDeploymentSchedule({ ...body, schedule: body.schedule }, callbacks);
	};
	return (
		<Form {...form}>
			<form
				className="space-y-4"
				onSubmit={(event) => void form.handleSubmit(save)(event)}
			>
				{form.formState.errors.root && (
					<p role="alert" className="text-sm text-destructive">
						{form.formState.errors.root.message}
					</p>
				)}
				<FormField
					control={form.control}
					name="active"
					render={({ field }) => (
						<FormItem>
							<FormLabel>Active</FormLabel>
							<FormControl>
								<Switch
									className="block"
									checked={field.value}
									onCheckedChange={field.onChange}
								/>
							</FormControl>
							<FormMessage />
						</FormItem>
					)}
				/>
				<fieldset className="space-y-3">
					<legend className="mb-2 text-sm font-medium">Recurrence</legend>
					<RRuleBuilder
						value={schedule.rrule}
						timezone={schedule.timezone}
						onChange={(rule) => form.setValue("schedule.rrule", rule)}
						onValidityChange={setValid}
					/>
				</fieldset>
				{readOnly && (
					<p className="text-sm text-muted-foreground">
						The rule and timezone are read-only. Save updates only Active and
						Parameter Overrides; the existing rule is left unchanged.
					</p>
				)}
				<FormField
					control={form.control}
					name="schedule.timezone"
					render={({ field }) => (
						<FormItem>
							<FormLabel>Timezone</FormLabel>
							<FormControl>
								{readOnly || !valid ? (
									<p className="text-sm">{field.value}</p>
								) : (
									<TimezoneSelect
										selectedValue={field.value}
										onSelect={(timezone) => {
											const parsed = parseRule(
												schedule.rrule,
												schedule.timezone,
											);
											if (parsed.supported)
												form.setValue("schedule", {
													rrule: serializeRule(parsed.value, timezone),
													timezone,
												});
										}}
									/>
								)}
							</FormControl>
							<FormMessage />
						</FormItem>
					)}
				/>
				{parameterOverrides && (
					<ScheduleParameterOverridesFormSection {...parameterOverrides} />
				)}
				<DialogFooter>
					<DialogClose asChild>
						<Button type="button" variant="outline">
							Close
						</Button>
					</DialogClose>
					<Button
						type="submit"
						disabled={!readOnly && !valid}
						loading={creating || updating || form.formState.isSubmitting}
					>
						Save
					</Button>
				</DialogFooter>
			</form>
		</Form>
	);
}
