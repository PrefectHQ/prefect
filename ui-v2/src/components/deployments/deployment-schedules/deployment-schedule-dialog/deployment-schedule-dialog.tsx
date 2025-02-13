import type { DeploymentSchedule } from "@/components/deployments/deployment-schedules/types";
import {
	Dialog,
	DialogContent,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { useState } from "react";
import { RRuleScheduleForm } from "./rrule-schedule-form";

type ScheduleTypes = "interval" | "cron" | "rrule";

type DeploymentScheduleDialogProps = {
	onOpenChange: (open: boolean) => void;
	open: boolean;
	scheduleToEdit?: DeploymentSchedule;
};

export const DeploymentScheduleDialog = ({
	onOpenChange,
	open,
	scheduleToEdit,
}: DeploymentScheduleDialogProps) => {
	const [scheduleTab, setScheduleTab] = useState<ScheduleTypes>("interval");

	const SCHEDULE_TAB_OPTIONS = [
		{
			value: "interval",
			label: "Interval",
			Component: () => <div>TODO: Interval form</div>,
		},
		{
			value: "cron",
			label: "Cron",
			Component: () => <div>TODO: Cron Form</div>,
		},
		{ value: "rrule", label: "RRule", Component: () => <RRuleScheduleForm /> },
	] as const;

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent aria-describedby={undefined}>
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
