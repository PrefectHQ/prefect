import { zodResolver } from "@hookform/resolvers/zod";
import { Link } from "@tanstack/react-router";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { Form, FormMessage } from "@/components/ui/form";
import { Stepper } from "@/components/ui/stepper";
import { useStepper } from "@/hooks/use-stepper";
import { ActionsStep } from "./actions-step";
import { AutomationWizardSchema } from "./automation-schema";
import { DetailsStep } from "./details-step";
import { TriggerStep } from "./trigger-step";

type AutomationWizardFormInput = z.input<typeof AutomationWizardSchema>;
type AutomationWizardFormOutput = z.output<typeof AutomationWizardSchema>;

const WIZARD_STEPS = ["Trigger", "Actions", "Details"] as const;
type WizardStep = (typeof WIZARD_STEPS)[number];

const DEFAULT_FORM_VALUES = {
	actions: [{ type: undefined }],
	trigger: {
		type: "event" as const,
		posture: "Reactive" as const,
		threshold: 1,
		within: 0,
	},
};

export type AutomationWizardProps = {
	defaultValues?: Partial<AutomationWizardFormInput>;
	onSubmit: (values: AutomationWizardFormOutput) => void;
	submitLabel?: string;
	isSubmitting?: boolean;
};

export const AutomationWizard = ({
	defaultValues = {},
	onSubmit,
	submitLabel = "Save",
	isSubmitting = false,
}: AutomationWizardProps) => {
	const isEditMode = Boolean(
		defaultValues && Object.keys(defaultValues).length > 0,
	);
	const initialVisitedSteps = isEditMode
		? new Set([0, 1, 2])
		: new Set<number>([0]);
	const stepper = useStepper(WIZARD_STEPS.length, 0, initialVisitedSteps);
	const form = useForm<
		AutomationWizardFormInput,
		unknown,
		AutomationWizardFormOutput
	>({
		resolver: zodResolver(AutomationWizardSchema),
		defaultValues: {
			...DEFAULT_FORM_VALUES,
			...defaultValues,
		} as AutomationWizardFormInput,
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
						<CardContent>
							{WIZARD_STEPS_MAP[currentStep].render()}
							<FormMessage>{form.formState.errors.root?.message}</FormMessage>
						</CardContent>
						<CardFooter className="mt-6 flex gap-2 justify-end">
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
								<Button key="save" type="submit" loading={isSubmitting}>
									{submitLabel}
								</Button>
							) : (
								<Button
									key="next"
									type="button"
									onClick={() => void handleIncrementStep(currentStep)}
								>
									Next
								</Button>
							)}
						</CardFooter>
					</Card>
				</div>
			</form>
		</Form>
	);
};
