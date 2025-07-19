import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Form, FormMessage } from "@/components/ui/form";
import { Stepper } from "@/components/ui/stepper";
import { ConfigurationStep } from "./configuration-step";
import {
	useWorkPoolCreateWizard,
	WIZARD_STEPS,
	type WizardStep,
} from "./hooks/use-work-pool-create-wizard";
import {
	useWorkPoolValidation,
	type WorkPoolSchema,
} from "./hooks/use-work-pool-validation";
import { InformationStep } from "./information-step";
import { InfrastructureTypeStep } from "./infrastructure-type-step";

export const WorkPoolCreateWizard = () => {
	const {
		stepper,
		workPoolData,
		updateWorkPoolData,
		submit,
		cancel,
		isSubmitting,
		currentStep,
	} = useWorkPoolCreateWizard();

	const { validateInfrastructureType, validateInformation, schemas } =
		useWorkPoolValidation();

	const form = useForm<WorkPoolSchema>({
		resolver: zodResolver(schemas.complete),
		defaultValues: {
			name: workPoolData.name || "",
			type: workPoolData.type || "",
			description: workPoolData.description,
			concurrencyLimit: workPoolData.concurrencyLimit,
			baseJobTemplate: workPoolData.baseJobTemplate,
			isPaused: workPoolData.isPaused,
		},
		values: {
			name: workPoolData.name || "",
			type: workPoolData.type || "",
			description: workPoolData.description,
			concurrencyLimit: workPoolData.concurrencyLimit,
			baseJobTemplate: workPoolData.baseJobTemplate,
			isPaused: workPoolData.isPaused,
		},
	});

	const WIZARD_STEPS_MAP = {
		"Infrastructure Type": {
			render: () => (
				<InfrastructureTypeStep
					value={workPoolData.type}
					onChange={(type) => {
						updateWorkPoolData({ type });
						// Auto-advance to next step after selection
						stepper.incrementStep();
					}}
				/>
			),
			validate: () => {
				const result = validateInfrastructureType(workPoolData);
				if (!result.isValid && result.errors.type) {
					form.setError("type", { message: result.errors.type[0] });
				}
				return result.isValid;
			},
		},
		Details: {
			render: () => (
				<InformationStep values={workPoolData} onChange={updateWorkPoolData} />
			),
			validate: () => {
				const result = validateInformation(workPoolData);
				if (!result.isValid) {
					Object.entries(result.errors).forEach(([field, errors]) => {
						if (errors && errors.length > 0) {
							form.setError(field as keyof WorkPoolSchema, {
								message: errors[0],
							});
						}
					});
				}
				return result.isValid;
			},
		},
		Configuration: {
			render: () => (
				<ConfigurationStep
					workPoolType={workPoolData.type || ""}
					value={workPoolData.baseJobTemplate}
					onChange={(baseJobTemplate) =>
						updateWorkPoolData({ baseJobTemplate })
					}
				/>
			),
			validate: () => true, // Configuration step validation is handled by the schema form
		},
	} as const;

	const handleIncrementStep = (step: WizardStep) => {
		const isValid = WIZARD_STEPS_MAP[step].validate();
		if (isValid) {
			stepper.incrementStep();
		}
	};

	const handleSubmit = async () => {
		await submit();
	};

	return (
		<Form {...form}>
			<form
				onSubmit={(e) => {
					e.preventDefault();
					void handleSubmit();
				}}
			>
				<div className="flex flex-col gap-8">
					<Stepper
						steps={WIZARD_STEPS}
						currentStepNum={stepper.currentStep}
						onClick={(step) => {
							if (stepper.visitedStepsSet.has(step.stepNum)) {
								stepper.changeStep(step.stepNum);
							}
						}}
						completedSteps={stepper.completedStepsSet}
						visitedSteps={stepper.visitedStepsSet}
					/>
					<Card className="p-6">
						{WIZARD_STEPS_MAP[currentStep].render()}
						<FormMessage>{form.formState.errors.root?.message}</FormMessage>
						<div className="mt-6 flex gap-2 justify-end">
							<Button type="button" variant="outline" onClick={cancel}>
								Cancel
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
								<Button
									type="button"
									onClick={() => {
										void handleSubmit();
									}}
									disabled={isSubmitting}
								>
									{isSubmitting ? "Creating..." : "Create"}
								</Button>
							) : (
								<Button
									type="button"
									onClick={() => {
					void handleIncrementStep(currentStep);
				}}
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
