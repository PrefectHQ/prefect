import { useState } from "react";
import { useSet } from "./use-set";
/**
 *
 * @param steps
 * @param startingStep
 * @returns state with declarative utilities to increment, decrement, or skip to a current state
 *
 * @example
 * ```ts
 * const STEPS = ['Trigger', 'Actions', 'Details'] as const
 *
 * const stepper = useStepper(STEPS.length);
 *
 * return (
 * <div>
 *   <h2>Current Step: {STEPS[stepper.currentStep]}</h2>
 *   <ul>
 *     {STEPS.map((step, i) => (
 * 			<li key={i} onClick={() => stepper.setStep(i)}>{step}</li>
 * 		)}
 *   </ul>
 *   <div>
 *     <Button disabled={stepper.isStartingStep} onClick={stepper.decrementStep()}>Previous</Button>
 *     <Button onClick={stepper.incrementStep()}>{stepper.isFinalStep ? 'Save' : 'Next'}</Button>
 *   </div>
 * </div>
 * )
 * ```
 */
export const useStepper = (numSteps: number, startingStep = 0) => {
	const [currentStep, setCurrentStep] = useState(startingStep);
	const [visitedStepsSet, { add: addVisitedStep, reset: resetVisitedSteps }] =
		useSet(new Set<number>([0]));
	const [
		completedStepsSet,
		{ add: addCompletedStep, reset: resetCompletedSteps },
	] = useSet(new Set<number>());

	const incrementStep = () => {
		if (currentStep < numSteps - 1) {
			// Marks step as visited
			addCompletedStep(currentStep);
			addVisitedStep(currentStep + 1);
			setCurrentStep((curr) => curr + 1);
		}
	};

	const decrementStep = () => {
		if (currentStep > 0) {
			setCurrentStep((curr) => curr - 1);
		}
	};

	const changeStep = (stepNum: number) => {
		setCurrentStep(stepNum);
	};

	const reset = () => {
		resetCompletedSteps();
		resetVisitedSteps();
		setCurrentStep(startingStep);
	};

	const isFinalStep = currentStep === numSteps - 1;
	const isStartingStep = currentStep === 0;

	return {
		changeStep,
		completedStepsSet,
		currentStep,
		decrementStep,
		incrementStep,
		isFinalStep,
		isStartingStep,
		reset,
		visitedStepsSet,
	};
};
