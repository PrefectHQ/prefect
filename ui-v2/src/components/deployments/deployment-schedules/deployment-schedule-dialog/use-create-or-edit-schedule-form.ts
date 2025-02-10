import {
	useCreateDeploymentSchedule,
	useUpdateDeploymentSchedule,
} from "@/api/deployments";
import type { DeploymentSchedule } from "@/components/deployments/deployment-schedules/types";
import { useToast } from "@/hooks/use-toast";
import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

const intervalForm = z.object({
	active: z.boolean(),
	tab: z.literal("interval"),
	schedule: z
		.object({
			interval: z.number().default(3_600),
			anchor_date: z.date(),
			timezone: z.string().default("Etc/UTC"),
		})
		.transform((schema) => ({
			...schema,
			anchor_date: schema.anchor_date.toISOString(),
		})),
});

const cronForm = z.object({
	active: z.boolean(),
	tab: z.literal("cron"),
	schedule: z.object({
		cron: z.string(),
		timezone: z.string().default("Etc/UTC"),
		day_or: z.boolean().default(true),
	}),
});

const rruleform = z.object({
	active: z.boolean(),
	tab: z.literal("rrule"),
	schedule: z.object({
		rrule: z.string().default(""),
		timezone: z.string().nullable().default(null),
	}),
});

const formSchema = intervalForm.or(cronForm).or(rruleform);
export type FormSchema = z.infer<typeof formSchema>;

const DEFAULT_VALUES = {
	tab: "interval",
	active: true,
	schedule: {
		interval: 3_600,
		anchor_date: new Date(),
		timezone: "Etc/UTC",
		cron: "* * * * *",
		day_or: true,
	},
} as const;

type UseCreateOrEditScheduleFormOptions = {
	deployment_id: string;
	/** Schedule to edit. Pass undefined if creating a new limit */
	scheduleToEdit?: DeploymentSchedule;
	/** Callback after hitting Save or Update */
	onSubmit: () => void;
};

export const useCreateOrEditScheduleForm = ({
	deployment_id,
	scheduleToEdit,
	onSubmit,
}: UseCreateOrEditScheduleFormOptions) => {
	const { toast } = useToast();

	const { createDeploymentSchedule, status: createStatus } =
		useCreateDeploymentSchedule();
	const { updateDeploymentSchedule, status: updateStatus } =
		useUpdateDeploymentSchedule();

	const form = useForm<FormSchema>({
		resolver: zodResolver(formSchema),
		defaultValues: DEFAULT_VALUES,
	});

	// Sync form data with limit-to-edit data
	useEffect(() => {
		if (scheduleToEdit) {
			const { active, schedule } = scheduleToEdit;
			form.reset({ active, schedule });
		} else {
			form.reset(DEFAULT_VALUES);
		}
	}, [form, scheduleToEdit]);

	const saveOrUpdate = (values: z.infer<typeof formSchema>) => {
		console.log({ values });
		const { active, tab, schedule } = values;
		let scheduleBody: FormSchema["schedule"];
		switch (tab) {
			case "interval":
				scheduleBody = {
					anchor_date: schedule.anchor_date,
					interval: schedule.interval,
					timezone: schedule.timezone,
				};
				break;
			case "cron":
				scheduleBody = {
					cron: schedule.cron,
					day_or: schedule.day_or,
					timezone: schedule.timezone,
				};
				break;
			case "rrule":
				scheduleBody = {
					rrule: schedule.rrule,
					timezone: schedule.timezone,
				};
				break;
			default:
				throw new Error("Unexpected 'tab' type");
		}

		const onSettled = () => {
			form.reset(DEFAULT_VALUES);
			onSubmit();
		};

		if (scheduleToEdit) {
			updateDeploymentSchedule(
				{
					deployment_id,
					schedule_id: scheduleToEdit.id,
					active,
					schedule: scheduleBody,
				},
				{
					onSuccess: () => {
						toast({ title: "Deployment schedule updated" });
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
					active,
					schedule: scheduleBody,
				},
				{
					onSuccess: () => {
						toast({ title: "Deployment schedule created" });
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

	return {
		form,
		saveOrUpdate,
		isLoading: createStatus === "pending" || updateStatus === "pending",
	};
};
