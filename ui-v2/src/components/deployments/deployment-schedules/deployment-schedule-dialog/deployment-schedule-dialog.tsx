import { useMemo, useState } from "react";
import type { DeploymentSchedule } from "@/api/deployments";
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

type ScheduleTypes = "interval" | "cron" | "rrule";

type DeploymentScheduleDialogProps = {
	deploymentId: string;
	onOpenChange: (open: boolean) => void;
	open: boolean;
	scheduleToEdit?: DeploymentSchedule;
	onSubmit: () => void;
};

export const DeploymentScheduleDialog = ({
	deploymentId,
	onOpenChange,
	open,
	scheduleToEdit,
	onSubmit,
}: DeploymentScheduleDialogProps) => {
	// Derive initial tab from scheduleToEdit
	const initialTab = useMemo(() => {
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
	}, [scheduleToEdit]);

	const [scheduleTab, setScheduleTab] = useState<ScheduleTypes>(initialTab);

	const SCHEDULE_TAB_OPTIONS = [
		{
			value: "interval",
			label: "Interval",
			Component: () => (
				<IntervalScheduleForm
					deployment_id={deploymentId}
					onSubmit={onSubmit}
					scheduleToEdit={scheduleToEdit}
				/>
			),
		},
		{
			value: "cron",
			label: "Cron",
			Component: () => (
				<CronScheduleForm
					deployment_id={deploymentId}
					onSubmit={onSubmit}
					scheduleToEdit={scheduleToEdit}
				/>
			),
		},
		{ value: "rrule", label: "RRule", Component: () => <RRuleScheduleForm /> },
	] as const;

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent
				aria-describedby={undefined}
				key={scheduleToEdit?.id ?? "new"}
			>
				<DialogHeader>
					<DialogTitle>{scheduleToEdit ? "Edit" : "Add"} Schedule</DialogTitle>
				</DialogHeader>

				<Tabs defaultValue={SCHEDULE_TAB_OPTIONS[0].value} value={scheduleTab}>
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
					{SCHEDULE_TAB_OPTIONS.map(({ value, Component }) => (
						<TabsContent key={value} value={value}>
							<Component />
						</TabsContent>
					))}
				</Tabs>
			</DialogContent>
		</Dialog>
	);
};
