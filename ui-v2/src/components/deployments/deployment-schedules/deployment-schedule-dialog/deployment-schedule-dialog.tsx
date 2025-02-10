import type { DeploymentSchedule } from "@/components/deployments/deployment-schedules/types";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogFooter,
	DialogHeader,
	DialogTitle,
	DialogTrigger,
} from "@/components/ui/dialog";
import { Form, FormMessage } from "@/components/ui/form";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { CronScheduleForm } from "./cron-schedule-form";
import { IntervalScheduleForm } from "./interval-schedule-form";
import { RRuleScheduleForm } from "./rrule-schedule-form";
import { useCreateOrEditScheduleForm } from "./use-create-or-edit-schedule-form";

type DeploymentScheduleDialogProps = {
	deployment_id: string;
	onOpenChange: (open: boolean) => void;
	onSubmit: () => void;
	open: boolean;
	scheduleToEdit?: DeploymentSchedule;
};

export const DeploymentScheduleDialog = ({
	deployment_id,
	onOpenChange,
	onSubmit,
	open,
	scheduleToEdit,
}: DeploymentScheduleDialogProps) => {
	const { form, saveOrUpdate, isLoading } = useCreateOrEditScheduleForm({
		deployment_id,
		onSubmit,
		scheduleToEdit,
	});

	const SCHEDULE_TAB_OPTIONS = [
		{
			value: "interval",
			label: "Interval",
			Component: () => <IntervalScheduleForm form={form} />,
		},
		{
			value: "cron",
			label: "Cron",
			Component: () => <CronScheduleForm form={form} />,
		},
		{ value: "rrule", label: "RRule", Component: () => <RRuleScheduleForm /> },
	] as const;

	const scheduleTab = form.watch("tab");

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent aria-describedby={undefined}>
				<DialogHeader>
					<DialogTitle>{scheduleToEdit ? "Edit" : "Add"} Schedule</DialogTitle>
				</DialogHeader>

				<Form {...form}>
					<form
						onSubmit={(e) => void form.handleSubmit(saveOrUpdate)(e)}
						className="space-y-4"
					>
						<FormMessage>{form.formState.errors.root?.message}</FormMessage>
						<Tabs
							defaultValue={SCHEDULE_TAB_OPTIONS[0].value}
							value={scheduleTab}
						>
							<TabsList>
								{SCHEDULE_TAB_OPTIONS.map(({ value, label }) => (
									<TabsTrigger
										key={value}
										value={value}
										onClick={() => form.setValue("tab", value)}
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
						<DialogFooter>
							<DialogTrigger asChild>
								<Button variant="outline">Close</Button>
							</DialogTrigger>
							<Button type="submit" loading={isLoading}>
								Save
							</Button>
						</DialogFooter>
					</form>
				</Form>
			</DialogContent>
		</Dialog>
	);
};
