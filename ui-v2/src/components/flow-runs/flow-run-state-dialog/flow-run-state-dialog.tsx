import { useSetFlowRunState } from "@/api/flow-runs";
import type { FlowRun } from "@/api/flow-runs";
import type { components } from "@/api/prefect";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { StateBadge } from "@/components/ui/state-badge";
import { Textarea } from "@/components/ui/textarea";
import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

// Flow states with display names
const FLOW_STATES = {
	COMPLETED: "Completed",
	RUNNING: "Running",
	SCHEDULED: "Scheduled",
	PENDING: "Pending",
	FAILED: "Failed",
	CANCELLED: "Cancelled",
	CANCELLING: "Cancelling",
	CRASHED: "Crashed",
	PAUSED: "Paused",
} as const satisfies Record<
	components["schemas"]["StateType"],
	Capitalize<Lowercase<components["schemas"]["StateType"]>>
>;
type FlowStates = keyof typeof FLOW_STATES;

const formSchema = z.object({
	state: z.enum(Object.keys(FLOW_STATES) as [FlowStates, ...FlowStates[]]),
	message: z.string().optional().default(""),
	force: z.boolean().default(false),
});

type FlowRunStateFormValues = z.infer<typeof formSchema>;

export type FlowRunStateDialogProps = {
	flowRun: FlowRun;
	open: boolean;
	onOpenChange: (open: boolean) => void;
};

export const FlowRunStateDialog = ({
	flowRun,
	open,
	onOpenChange,
}: FlowRunStateDialogProps) => {
	const [isSubmitting, setIsSubmitting] = useState(false);
	const { setFlowRunState } = useSetFlowRunState();

	// Find first state that is not the current state for default value
	const getDefaultState = (): FlowStates => {
		if (!flowRun.state?.type) return "PENDING";

		const currentState = flowRun.state.type;
		const allStates = Object.keys(FLOW_STATES) as FlowStates[];

		const alternativeState = allStates.find((state) => state !== currentState);
		return alternativeState || "PENDING";
	};

	const form = useForm<FlowRunStateFormValues>({
		resolver: zodResolver(formSchema),
		defaultValues: {
			state: getDefaultState(),
			message: "",
			force: false,
		},
	});

	// Get the current state from the form
	const selectedState = form.watch("state");
	const isCurrentState = selectedState === flowRun.state?.type;

	// Check if form can be submitted (state has changed)
	const isSubmitDisabled = isSubmitting || isCurrentState;

	const onSubmit = (values: FlowRunStateFormValues) => {
		// Don't submit if the state hasn't changed
		if (isCurrentState) {
			return;
		}

		setIsSubmitting(true);

		// Make the API call to change the state
		setFlowRunState(
			{
				id: flowRun.id,
				state: values.state,
				message: values.message || null,
				force: values.force,
			},
			{
				onSuccess: () => {
					toast.success(
						<div className="flex items-center gap-2">
							Flow run state changed to{" "}
							<StateBadge
								type={values.state}
								name={FLOW_STATES[values.state]}
							/>
						</div>,
					);
					setIsSubmitting(false);
					onOpenChange(false);
				},
				onError: (error) => {
					const message =
						error.message || "Unknown error while changing flow run state.";
					toast.error(message);
					setIsSubmitting(false);
					console.error("Error changing flow run state:", error);
				},
			},
		);
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent aria-describedby={undefined}>
				<DialogHeader>
					<DialogTitle>Change Flow Run State</DialogTitle>
				</DialogHeader>

				<Form {...form}>
					<form
						onSubmit={(e) => void form.handleSubmit(onSubmit)(e)}
						className="space-y-4"
					>
						<div className="mb-4">
							<FormLabel className="mb-2 block">
								Current Flow Run State
							</FormLabel>
							{flowRun.state && (
								<StateBadge
									type={flowRun.state.type}
									name={flowRun.state.name}
								/>
							)}
						</div>

						<FormField
							control={form.control}
							name="state"
							render={({ field }) => (
								<FormItem className="w-full">
									<FormLabel>Desired Flow Run State</FormLabel>
									<FormControl>
										<Select {...field} onValueChange={field.onChange}>
											<SelectTrigger
												aria-label="select state"
												className="w-full"
											>
												<SelectValue placeholder="Select state">
													{field.value && (
														<StateBadge
															type={field.value}
															name={FLOW_STATES[field.value]}
														/>
													)}
												</SelectValue>
											</SelectTrigger>
											<SelectContent className="w-full min-w-[300px]">
												<SelectGroup>
													{Object.keys(FLOW_STATES).map((key) => (
														<SelectItem
															key={key}
															value={key}
															className="flex items-center"
															disabled={key === flowRun.state?.type}
														>
															<StateBadge
																type={key as components["schemas"]["StateType"]}
																name={FLOW_STATES[key as FlowStates]}
															/>
														</SelectItem>
													))}
												</SelectGroup>
											</SelectContent>
										</Select>
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>

						<FormField
							control={form.control}
							name="message"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Reason (Optional)</FormLabel>
									<FormControl>
										<Textarea
											{...field}
											placeholder="State changed manually via UI"
										/>
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>

						<div className="flex flex-col gap-2 pt-4">
							{isCurrentState && (
								<p className="text-sm text-muted-foreground">
									Please select a different state than the current one to
									continue
								</p>
							)}
							<div className="flex justify-end space-x-2">
								<Button
									type="button"
									variant="outline"
									onClick={() => onOpenChange(false)}
								>
									Close
								</Button>
								<Button type="submit" disabled={isSubmitDisabled}>
									Change
								</Button>
							</div>
						</div>
					</form>
				</Form>
			</DialogContent>
		</Dialog>
	);
};
