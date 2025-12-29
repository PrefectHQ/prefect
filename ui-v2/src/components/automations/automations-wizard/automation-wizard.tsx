import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { useCreateAutomation } from "@/api/automations";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Form, FormMessage } from "@/components/ui/form";
import { Stepper } from "@/components/ui/stepper";
import { useStepper } from "@/hooks/use-stepper";
import { ActionsStep } from "./actions-step";
import {
	AutomationWizardSchema,
	type AutomationWizardSchema as TAutomationWizardSchema,
} from "./automation-schema";
import { DetailsStep } from "./details-step";
import { transformWizardToApiPayload } from "./transform-wizard-to-api";
import { TriggerStep } from "./trigger-step";

const WIZARD_STEPS = ["Trigger", "Actions", "Details"] as const;
type WizardStep = (typeof WIZARD_STEPS)[number];

export const AutomationWizard = () => {
	const { createAutomation, isPending } = useCreateAutomation();
	const navigate = useNavigate();
	const stepper = useStepper(WIZARD_STEPS.length);
	const form = useForm({
		resolver: zodResolver(AutomationWizardSchema),
		defaultValues: {
			actions: [{ type: undefined }],
			trigger: {
				type: "event",
				posture: "Reactive",
				threshold: 1,
				within: 0,
			},
		},
	});

	const currentStep = WIZARD_STEPS[stepper.currentStep];
	const WIZARD_STEPS_MAP = {
		Trigger: {
			render: () => <TriggerStep />,
			trigger: () => form.trigger("trigger"),
		},
		Actions: {
			render: () => <ActionsStep />,
			trigger: () => form.trigger("actions"),
		},
		Details: {
			render: () => <DetailsStep />,
			trigger: () => form.trigger(["description", "name"]),
		},
	} as const;

	const handleIncrementStep = async (step: WizardStep) => {
		const isValid = await WIZARD_STEPS_MAP[step].trigger();
		if (isValid) {
			stepper.incrementStep();
		}
	};

	const onSubmit = (values: TAutomationWizardSchema) => {
		const automationData = transformWizardToApiPayload(values);

		createAutomation(automationData, {
			onSuccess: () => {
				toast.success("Automation created successfully");
				void navigate({ to: "/automations" });
			},
			onError: (error) => {
				toast.error(`Failed to create automation: ${error.message}`);
			},
		});
	};

	return (
		<Form {...form}>
			<form onSubmit={(e) => void form.handleSubmit(onSubmit)(e)}>
				<div className="flex flex-col gap-8">
					<Stepper
						steps={WIZARD_STEPS}
						currentStepNum={stepper.currentStep}
						onClick={(step) => stepper.changeStep(step.stepNum)}
						completedSteps={stepper.completedStepsSet}
						visitedSteps={stepper.visitedStepsSet}
					/>
					<Card className="p-4 pt-8">
						{WIZARD_STEPS_MAP[currentStep].render()}
						<FormMessage>{form.formState.errors.root?.message}</FormMessage>
						<div className="mt-6 flex gap-2 justify-end">
							<Button type="button" variant="outline">
								<Link to="/automations">Cancel</Link>
							</Button>
							<Button
								disabled={stepper.isStartingStep}
								type="button"
								variant="outline"
								onClick={stepper.decrementStep}
							>
								Previous
							</Button>
							{stepper.isFinalStep ? (
								<Button type="submit" loading={isPending}>
									Save
								</Button>
							) : (
								<Button
									type="button"
									onClick={() => void handleIncrementStep(currentStep)}
								>
									Next
								</Button>
							)}
						</div>
					</Card>
				</div>
			</form>
		</Form>
	);
};
