import { useNavigate } from "@tanstack/react-router";
import { useCallback, useState } from "react";
import { toast } from "sonner";
import { useCreateWorkPoolMutation } from "@/api/work-pools";
import { useStepper } from "@/hooks/use-stepper";
import type { WorkPoolCreate, WorkPoolFormValues } from "../types";

export const WIZARD_STEPS = [
	"Infrastructure Type",
	"Details",
	"Configuration",
] as const;
export type WizardStep = (typeof WIZARD_STEPS)[number];

export const useWorkPoolCreateWizard = () => {
	const navigate = useNavigate();
	const createWorkPoolMutation = useCreateWorkPoolMutation();
	const stepper = useStepper(WIZARD_STEPS.length);

	const [workPoolData, setWorkPoolData] = useState<WorkPoolFormValues>({
		isPaused: false,
	});

	const updateWorkPoolData = useCallback(
		(data: Partial<WorkPoolFormValues>) => {
			setWorkPoolData((prev) => ({ ...prev, ...data }));
		},
		[],
	);

	const submit = useCallback(async () => {
		if (!workPoolData.name || !workPoolData.type) {
			toast.error("Missing required fields");
			return;
		}

		// The ConfigurationStep now passes the complete base_job_template structure
		// with both job_configuration and variables
		const workPoolCreate: WorkPoolCreate = {
			name: workPoolData.name,
			type: workPoolData.type,
			description: workPoolData.description || null,
			concurrency_limit: workPoolData.concurrencyLimit || null,
			is_paused: workPoolData.isPaused || false,
			base_job_template: workPoolData.baseJobTemplate,
		};

		try {
			const createdWorkPool =
				await createWorkPoolMutation.mutateAsync(workPoolCreate);
			toast.success("Work pool created successfully");
			void navigate({ to: `/work-pools/work-pool/${createdWorkPool.name}` });
		} catch (error) {
			// Error handling is done by the mutation's onError callback
			console.error("Failed to create work pool:", error);
		}
	}, [workPoolData, createWorkPoolMutation, navigate]);

	const cancel = useCallback(() => {
		void navigate({ to: "/work-pools" });
	}, [navigate]);

	return {
		stepper,
		workPoolData,
		updateWorkPoolData,
		submit,
		cancel,
		isSubmitting: createWorkPoolMutation.isPending,
		submitError: createWorkPoolMutation.error,
		currentStep: WIZARD_STEPS[stepper.currentStep],
	};
};
