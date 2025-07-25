import { zodResolver } from "@hookform/resolvers/zod";
import { useSuspenseQuery } from "@tanstack/react-query";
import { useRouter } from "@tanstack/react-router";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { buildListWorkPoolTypesQuery } from "@/api/collections/collections";
import { useCreateWorkPool, type WorkPoolCreate } from "@/api/work-pools";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Form } from "@/components/ui/form";
import { Stepper } from "@/components/ui/stepper";
import { useStepper } from "@/hooks/use-stepper";
import { InformationStep } from "./information-step";
import { workPoolInformationSchema } from "./information-step/schema";
import { InfrastructureConfigurationStep } from "./infrastructure-configuration-step";
import { infrastructureConfigurationSchema } from "./infrastructure-configuration-step/schema";
import { InfrastructureTypeStep } from "./infrastructure-type-step";

const STEPS = ["Infrastructure Type", "Details", "Configuration"] as const;

// Combined schema for all steps
const workPoolCreateSchema = z.object({
	type: z.string().min(1, "Infrastructure type is required"),
	...workPoolInformationSchema.shape,
	...infrastructureConfigurationSchema.shape,
});

type WorkPoolCreateFormValues = z.infer<typeof workPoolCreateSchema>;

export function WorkPoolCreateWizard() {
	const router = useRouter();
	const { createWorkPool, isPending } = useCreateWorkPool();
	const { data: workersResponse = {} } = useSuspenseQuery(
		buildListWorkPoolTypesQuery(),
	);

	// Stepper state management
	const stepper = useStepper(STEPS.length);

	// Form state management
	const form = useForm<WorkPoolCreateFormValues>({
		resolver: zodResolver(workPoolCreateSchema),
		defaultValues: {
			description: null,
			concurrencyLimit: null,
		},
	});

	const workerType = form.watch("type");

	useEffect(() => {
		const workerInfo = Object.values(workersResponse).find(
			(collection) =>
				collection &&
				typeof collection === "object" &&
				Object.values(collection).find(
					(workerInfo) =>
						workerInfo &&
						typeof workerInfo === "object" &&
						"type" in workerInfo &&
						(workerInfo as { type: string }).type === workerType,
				),
		) as Record<string, unknown> | undefined;
		if (
			workerInfo &&
			workerType in workerInfo &&
			typeof workerInfo[workerType] === "object" &&
			workerInfo[workerType] &&
			"default_base_job_configuration" in workerInfo[workerType]
		) {
			form.setValue(
				"baseJobTemplate",
				workerInfo[workerType].default_base_job_configuration as Record<
					string,
					unknown
				>,
			);
		}
	}, [workersResponse, form, workerType]);

	const handleNext = async () => {
		const fieldsToValidate = getFieldsForStep(stepper.currentStep);
		const isStepValid = await form.trigger(fieldsToValidate);

		if (isStepValid) {
			if (stepper.isFinalStep) {
				await handleSubmit();
			} else {
				stepper.incrementStep();
			}
		}
	};

	const handleBack = () => {
		stepper.decrementStep();
	};

	const handleCancel = () => {
		void router.navigate({ to: "/work-pools" });
	};

	const handleSubmit = async () => {
		const isValid = await form.trigger();
		if (!isValid) return;

		const formData = form.getValues();

		// Validate required fields before submission
		if (!formData.name || !formData.type) {
			toast.error("Please fill in all required fields");
			return;
		}

		const workPoolData: WorkPoolCreate = {
			name: formData.name,
			type: formData.type,
			description: formData.description,
			is_paused: false,
			concurrency_limit: formData.concurrencyLimit,
			base_job_template:
				(formData.baseJobTemplate as Record<string, unknown>) || {},
		};

		createWorkPool(workPoolData, {
			onSuccess: (data) => {
				toast.success(`Work pool "${formData.name}" created successfully`);
				void router.navigate({
					to: "/work-pools/work-pool/$workPoolName",
					params: { workPoolName: data.data?.name || formData.name },
				});
			},
			onError: (error) => {
				toast.error(`Failed to create work pool: ${error.message}`);
			},
		});
	};

	const getFieldsForStep = (
		stepIndex: number,
	): (keyof WorkPoolCreateFormValues)[] => {
		switch (stepIndex) {
			case 0:
				return ["type"];
			case 1:
				return ["name", "description", "concurrencyLimit"];
			case 2:
				return ["baseJobTemplate"];
			default:
				return [];
		}
	};

	const renderCurrentStep = () => {
		switch (stepper.currentStep) {
			case 0:
				return <InfrastructureTypeStep />;
			case 1:
				return <InformationStep />;
			case 2:
				return <InfrastructureConfigurationStep />;
			default:
				return null;
		}
	};

	return (
		<div className="space-y-6">
			<Card>
				<CardHeader>
					<CardTitle>Create Work Pool</CardTitle>
				</CardHeader>
				<CardContent>
					<Stepper
						currentStepNum={stepper.currentStep}
						steps={STEPS}
						onClick={({ stepNum }) => {
							if (stepper.visitedStepsSet.has(stepNum)) {
								stepper.changeStep(stepNum);
							}
						}}
						completedSteps={stepper.completedStepsSet}
						visitedSteps={stepper.visitedStepsSet}
					/>
				</CardContent>
			</Card>

			<Card>
				<CardContent className="pt-6">
					<Form {...form}>
						<form className="space-y-6">{renderCurrentStep()}</form>
					</Form>
				</CardContent>
			</Card>

			{/* Navigation buttons */}
			<div className="flex justify-between">
				<div>
					{!stepper.isStartingStep && (
						<Button variant="outline" onClick={handleBack} disabled={isPending}>
							Back
						</Button>
					)}
					<Button
						variant="ghost"
						onClick={handleCancel}
						disabled={isPending}
						className="ml-2"
					>
						Cancel
					</Button>
				</div>
				<Button onClick={() => void handleNext()} disabled={isPending}>
					{isPending
						? "Creating..."
						: stepper.isFinalStep
							? "Create Work Pool"
							: "Next"}
				</Button>
			</div>
		</div>
	);
}
