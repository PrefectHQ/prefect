import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import type { DeploymentSchedule } from "@/api/deployments";
import {
	useCreateDeploymentSchedule,
	useUpdateDeploymentSchedule,
} from "@/api/deployments";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Icon } from "@/components/ui/icons";
import { Input } from "@/components/ui/input";
import {
	Popover,
	PopoverContent,
	PopoverTrigger,
} from "@/components/ui/popover";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { TimezoneSelect } from "@/components/ui/timezone-select";
import { cn } from "@/utils";
import { formatDate } from "@/utils/date";

const INTERVALS = [
	{ label: "Seconds", value: "seconds" },
	{ label: "Minutes", value: "minutes" },
	{ label: "Hours", value: "hours" },
	{ label: "Days", value: "days" },
] as const;
type Intervals = (typeof INTERVALS)[number]["value"];

const INTERVAL_SECONDS = {
	seconds: 1,
	minutes: 60,
	hours: 3_600,
	days: 24 * 3600,
} satisfies Record<Intervals, number>;

const parseIntervalToTime = (
	interval: number,
): { interval_value: number; interval_time: Intervals } => {
	let remainingSeconds = interval;

	const days = Math.floor(interval / INTERVAL_SECONDS.days);
	remainingSeconds %= INTERVAL_SECONDS.days;
	if (remainingSeconds === 0) {
		return { interval_value: days, interval_time: "days" } as const;
	}

	const hours = Math.floor(interval / INTERVAL_SECONDS.hours);
	remainingSeconds %= INTERVAL_SECONDS.hours;
	if (remainingSeconds === 0) {
		return { interval_value: hours, interval_time: "hours" } as const;
	}

	const minutes = Math.floor(interval / INTERVAL_SECONDS.minutes);
	remainingSeconds %= INTERVAL_SECONDS.minutes;
	if (remainingSeconds === 0) {
		return { interval_value: minutes, interval_time: "minutes" } as const;
	}

	return {
		interval_value: remainingSeconds,
		interval_time: "seconds",
	} as const;
};

const formSchema = z.object({
	active: z.boolean(),
	schedule: z.object({
		/** Coerce to solve common issue of transforming a string number to a number type */
		interval_value: z.number().or(z.string()).pipe(z.coerce.number()),
		interval_time: z.enum(["seconds", "minutes", "hours", "days"]),
		anchor_date: z.date(),
		timezone: z.string().default("Etc/UTC"),
	}),
});
type FormSchema = z.infer<typeof formSchema>;

const DEFAULT_VALUES: FormSchema = {
	active: true,
	schedule: {
		interval_value: 60,
		interval_time: "minutes",
		anchor_date: new Date(),
		timezone: "Etc/UTC",
	},
};

export type IntervalScheduleFormProps = {
	deployment_id: string;
	/** Schedule to edit. Pass undefined if creating a new limit */
	scheduleToEdit?: DeploymentSchedule;
	/** Callback after hitting Save or Update */
	onSubmit: () => void;
};

export const IntervalScheduleForm = ({
	deployment_id,
	scheduleToEdit,
	onSubmit,
}: IntervalScheduleFormProps) => {
	const { createDeploymentSchedule, isPending: createPending } =
		useCreateDeploymentSchedule();
	const { updateDeploymentSchedule, isPending: updatePending } =
		useUpdateDeploymentSchedule();

	const form = useForm({
		resolver: zodResolver(formSchema),
		defaultValues: DEFAULT_VALUES,
	});

	// Sync form data with scheduleToEdit data
	useEffect(() => {
		if (scheduleToEdit) {
			const { active, schedule } = scheduleToEdit;
			if ("interval" in schedule) {
				const { interval, anchor_date, timezone } = schedule;
				const { interval_value, interval_time } = parseIntervalToTime(interval);
				form.reset({
					active,
					schedule: {
						interval_value,
						interval_time,
						anchor_date: anchor_date ? new Date(anchor_date) : new Date(),
						timezone: timezone ?? "Etc/UTC",
					},
				});
			}
		} else {
			form.reset(DEFAULT_VALUES);
		}
	}, [form, scheduleToEdit]);

	const handleSave = (values: FormSchema) => {
		const onSettled = () => {
			form.reset(DEFAULT_VALUES);
			onSubmit();
		};

		if (scheduleToEdit) {
			updateDeploymentSchedule(
				{
					deployment_id,
					schedule_id: scheduleToEdit.id,
					active: values.active,
					schedule: {
						interval:
							values.schedule.interval_value *
							INTERVAL_SECONDS[values.schedule.interval_time],
						anchor_date: values.schedule.anchor_date.toISOString(),
						timezone: values.schedule.timezone,
					},
				},
				{
					onSuccess: () => {
						toast.success("Deployment schedule updated");
					},
					onError: (error) => {
						const message =
							error.message ||
							"Unknown error while updating deployment schedule.";
						form.setError("root", { message });
					},
					onSettled,
				},
			);
		} else {
			createDeploymentSchedule(
				{
					deployment_id,
					active: values.active,
					schedule: {
						interval:
							values.schedule.interval_value *
							INTERVAL_SECONDS[values.schedule.interval_time],
						anchor_date: values.schedule.anchor_date.toISOString(),
						timezone: values.schedule.timezone,
					},
				},
				{
					onSuccess: () => {
						toast.success("Deployment schedule created");
					},
					onError: (error) => {
						const message =
							error.message ||
							"Unknown error while creating deployment schedule.";
						form.setError("root", {
							message,
						});
					},
					onSettled,
				},
			);
		}
	};

	return (
		<Form {...form}>
			<form
				onSubmit={(e) => void form.handleSubmit(handleSave)(e)}
				className="space-y-4"
			>
				<FormMessage>{form.formState.errors.root?.message}</FormMessage>
				<div className="flex flex-col gap-4">
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
					<div className="flex gap-2">
						<div className="w-3/4">
							<FormField
								control={form.control}
								name="schedule.interval_value"
								render={({ field }) => (
									<FormItem>
										<FormLabel>Value</FormLabel>
										<FormControl>
											<Input {...field} />
										</FormControl>
										<FormMessage />
									</FormItem>
								)}
							/>
						</div>
						<FormField
							control={form.control}
							name="schedule.interval_time"
							render={({ field }) => {
								// nb: There's a select bug with shadcn that resets the value to "". For now, just have the users re-enter time interval
								return (
									<FormItem>
										<FormLabel>Interval</FormLabel>
										<Select
											onValueChange={field.onChange}
											defaultValue={field.value}
											value={field.value}
										>
											<FormControl>
												<SelectTrigger>
													<SelectValue placeholder="Select interval" />
												</SelectTrigger>
											</FormControl>
											<SelectContent>
												{INTERVALS.map(({ label, value }) => (
													<SelectItem key={value} value={value}>
														{label}
													</SelectItem>
												))}
											</SelectContent>
										</Select>
										<FormMessage />
									</FormItem>
								);
							}}
						/>
					</div>

					<FormField
						control={form.control}
						name="schedule.anchor_date"
						render={({ field }) => (
							<FormItem className="flex flex-col">
								<FormLabel>Anchor date</FormLabel>
								<Popover>
									<PopoverTrigger asChild>
										<FormControl>
											<Button
												variant="outline"
												className={cn(
													"w-full",
													!field.value && "text-muted-foreground",
												)}
											>
												{formatDate(field.value, "dateTime")}
												<Icon
													id="Calendar"
													className="ml-auto size-4 opacity-50"
												/>
											</Button>
										</FormControl>
									</PopoverTrigger>
									<PopoverContent className="w-auto p-0" align="start">
										<Calendar
											mode="single"
											selected={field.value}
											onSelect={field.onChange}
										/>
									</PopoverContent>
								</Popover>
								<FormMessage />
							</FormItem>
						)}
					/>
					<FormField
						control={form.control}
						name="schedule.timezone"
						render={({ field }) => (
							<FormItem>
								<FormLabel>Timezone</FormLabel>
								<FormControl>
									<TimezoneSelect
										selectedValue={field.value}
										onSelect={field.onChange}
									/>
								</FormControl>
								<FormMessage />
							</FormItem>
						)}
					/>
				</div>

				<DialogFooter>
					<DialogTrigger asChild>
						<Button variant="outline">Close</Button>
					</DialogTrigger>
					<Button type="submit" loading={createPending || updatePending}>
						Save
					</Button>
				</DialogFooter>
			</form>
		</Form>
	);
};
