import { Button } from "@/components/ui/button";
import { Stepper } from "@/components/ui/stepper";
import { useStepper } from "@/hooks/use-stepper";

const USAGE_STEPS = ["Trigger", "Actions", "Details"] as const;

export const StepperStory = () => {
	const stepper = useStepper(USAGE_STEPS.length);
	return (
		<div className="flex flex-col gap-4">
			<Stepper
				steps={USAGE_STEPS}
				currentStepNum={stepper.currentStep}
				onClick={(step) => stepper.changeStep(step.stepNum)}
				completedSteps={stepper.completedStepsSet}
				visitedSteps={stepper.visitedStepsSet}
			/>
			<div className="flex justify-between">
				<Button
					variant="secondary"
					disabled={stepper.isStartingStep}
					onClick={stepper.decrementStep}
				>
					Previous
				</Button>
				{stepper.isFinalStep ? (
					<Button onClick={stepper.reset}>Finish</Button>
				) : (
					<Button onClick={stepper.incrementStep}>Next</Button>
				)}
			</div>
		</div>
	);
};
