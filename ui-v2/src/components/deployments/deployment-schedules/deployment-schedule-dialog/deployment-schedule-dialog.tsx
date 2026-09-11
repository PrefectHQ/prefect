import { useState } from "react";
import type { Deployment, DeploymentSchedule } from "@/api/deployments";
import {
	Dialog,
	DialogContent,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CronScheduleForm } from "./cron-schedule-form";
import { IntervalScheduleForm } from "./interval-schedule-form";
import { RRuleScheduleForm } from "./rrule-schedule-form";
import { useScheduleParameterOverrides } from "./use-schedule-parameter-overrides";

type ScheduleTypes = "interval" | "cron" | "rrule";

const SCHEDULE_TAB_OPTIONS = [
	{ value: "interval", label: "Interval" },
	{ value: "cron", label: "Cron" },
	{ value: "rrule", label: "RRule" },
] as const satisfies { value: ScheduleTypes; label: string }[];

const getScheduleType = (
	scheduleToEdit?: DeploymentSchedule,
): ScheduleTypes => {
	if (!scheduleToEdit) {
		return "interval";
	}
	const { schedule } = scheduleToEdit;
	if ("interval" in schedule) {
		return "interval";
	}
	if ("cron" in schedule) {
		return "cron";
	}
	return "rrule";
};

type DeploymentScheduleDialogProps = {
	deployment: Deployment;
	onOpenChange: (open: boolean) => void;
	open: boolean;
	scheduleToEdit?: DeploymentSchedule;
	onSubmit: () => void;
};

export const DeploymentScheduleDialog = ({
	deployment,
	onOpenChange,
	open,
	scheduleToEdit,
	onSubmit,
}: DeploymentScheduleDialogProps) => (
	<Dialog open={open} onOpenChange={onOpenChange}>
		<DialogContent
			aria-describedby={undefined}
			className="max-h-[85vh] overflow-y-auto"
		>
			<DialogHeader>
				<DialogTitle>{scheduleToEdit ? "Edit" : "Add"} Schedule</DialogTitle>
			</DialogHeader>

			{open && (
				// nb: Remounted per schedule so form state starts from the schedule
				<DeploymentScheduleDialogForms
					key={`${deployment.id}-${scheduleToEdit?.id ?? "new-schedule"}`}
					deployment={deployment}
					scheduleToEdit={scheduleToEdit}
					onSubmit={onSubmit}
				/>
			)}
		</DialogContent>
	</Dialog>
);

type DeploymentScheduleDialogFormsProps = {
	deployment: Deployment;
	scheduleToEdit?: DeploymentSchedule;
	onSubmit: () => void;
};

const DeploymentScheduleDialogForms = ({
	deployment,
	scheduleToEdit,
	onSubmit,
}: DeploymentScheduleDialogFormsProps) => {
	const [scheduleTab, setScheduleTab] = useState<ScheduleTypes>(() =>
		getScheduleType(scheduleToEdit),
	);
	const parameterOverrides = useScheduleParameterOverrides(
		deployment,
		scheduleToEdit,
	);

	return (
		<Tabs value={scheduleTab}>
			<TabsList>
				{SCHEDULE_TAB_OPTIONS.map(({ value, label }) => (
					<TabsTrigger
						key={value}
						value={value}
						onClick={() => setScheduleTab(value)}
					>
						{label}
					</TabsTrigger>
				))}
			</TabsList>
			<TabsContent value="interval">
				<IntervalScheduleForm
					deployment_id={deployment.id}
					onSubmit={onSubmit}
					scheduleToEdit={scheduleToEdit}
					parameterOverrides={parameterOverrides}
				/>
			</TabsContent>
			<TabsContent value="cron">
				<CronScheduleForm
					deployment_id={deployment.id}
					onSubmit={onSubmit}
					scheduleToEdit={scheduleToEdit}
					parameterOverrides={parameterOverrides}
				/>
			</TabsContent>
			<TabsContent value="rrule">
				<RRuleScheduleForm />
			</TabsContent>
		</Tabs>
	);
};
