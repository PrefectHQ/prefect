import { zodResolver } from "@hookform/resolvers/zod";
import { CronExpressionParser } from "cron-parser";
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
import { CronInput } from "@/components/ui/cron-input";
import {
	Dialog,
	DialogContent,
	DialogFooter,
	DialogHeader,
	DialogTitle,
	DialogTrigger,
} from "@/components/ui/dialog";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Icon } from "@/components/ui/icons";
import { Switch } from "@/components/ui/switch";
import { TimezoneSelect } from "@/components/ui/timezone-select";
import { Typography } from "@/components/ui/typography";

const verifyCronValue = (cronValue: string) => {
	try {
		CronExpressionParser.parse(cronValue);
		return true;
	} catch {
		return false;
	}
};

const formSchema = z.object({
	active: z.boolean(),
	schedule: z.object({
		cron: z.string().refine(verifyCronValue),
		timezone: z.string().default("Etc/UTC"),
		day_or: z.boolean().default(true),
	}),
});
type FormSchema = z.infer<typeof formSchema>;

const DEFAULT_VALUES = {
	active: true,
	schedule: {
		cron: "* * * * *",
		timezone: "Etc/UTC",
		day_or: true,
	},
} satisfies FormSchema;

export type CronScheduleFormProps = {
	deployment_id: string;
	/** Schedule to edit. Pass undefined if creating a new limit */
	scheduleToEdit?: DeploymentSchedule;
	/** Callback after hitting Save or Update */
	onSubmit: () => void;
};

export const CronScheduleForm = ({
	deployment_id,
	scheduleToEdit,
	onSubmit,
}: CronScheduleFormProps) => {
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
			if ("cron" in schedule) {
				const { cron, day_or, timezone } = schedule;
				form.reset({
					active,
					schedule: {
						cron,
						day_or,
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
					...values,
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
					...values,
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
								name="schedule.cron"
								render={({ field }) => (
									<FormItem>
										<FormLabel>Value</FormLabel>
										<FormControl>
											<CronInput {...field} />
										</FormControl>
										<FormMessage />
									</FormItem>
								)}
							/>
						</div>
						<FormField
							control={form.control}
							name="schedule.day_or"
							render={({ field }) => (
								<FormItem>
									<FormLabel aria-label="Day Or">
										Day Or <DayOrDialog />
									</FormLabel>
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
					</div>
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

const DayOrDialog = () => {
	return (
		<Dialog>
			<DialogTrigger asChild>
				<button type="button" className="cursor-help">
					<Icon id="Info" className="size-4 inline" />
				</button>
			</DialogTrigger>
			<DialogContent aria-describedby={undefined}>
				<DialogHeader>
					<DialogTitle>Day Or</DialogTitle>
				</DialogHeader>
				<Typography>
					When the &quot;Day Or&quot; value is off, this schedule will connect
					day of the month and day of the week entries using OR logic; when on
					it will connect them using AND logic.
				</Typography>
			</DialogContent>
		</Dialog>
	);
};
