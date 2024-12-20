import { useState } from "react";

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
export const useStepper = (numSteps: number, startingStep: number = 0) => {
	const [currentStep, setCurrentStep] = useState(startingStep);

	const incrementStep = () => {
		if (currentStep < numSteps - 1) {
			setCurrentStep((curr) => curr + 1);
		}
	};

	const decrementStep = () => {
		if (currentStep > 0) {
			setCurrentStep((curr) => curr - 1);
		}
	};

	const reset = () => setCurrentStep(startingStep);

	const getIsStepCompleted = (stepNum: number) => stepNum < currentStep;
	const getIsCurrentStep = (stepNum: number) => stepNum === currentStep;
	const isFinalStep = currentStep === numSteps - 1;
	const isStartingStep = currentStep === 0;

	return {
		currentStep,
		decrementStep,
		getIsCurrentStep,
		getIsStepCompleted,
		incrementStep,
		isFinalStep,
		isStartingStep,
		reset,
		setCurrentStep,
	};
};
