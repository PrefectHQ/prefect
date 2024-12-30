import { useStepper } from "@/hooks/use-stepper";
import type { Meta, StoryObj } from "@storybook/react";
import { Button } from "./button";
import { Stepper } from "./stepper";

const meta: Meta<typeof Stepper> = {
	title: "UI/Stepper",
	component: Stepper,
	render: () => <StepperStory />,
};
export default meta;

export const story: StoryObj = { name: "Stepper" };

const STEPS = ["Trigger", "Actions", "Details"] as const;

const StepperStory = () => {
	const stepper = useStepper(STEPS.length);

	return (
		<div className="flex flex-col gap-4">
			<Stepper
				steps={STEPS}
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
