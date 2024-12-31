import { cn } from "@/lib/utils";

import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icons";
import { Typography } from "@/components/ui/typography";

type StepperProps = {
	currentStepNum: number;
	steps: Array<string> | ReadonlyArray<string>;
	onClick: ({
		stepName,
		stepNum,
	}: { stepName: string; stepNum: number }) => void;
	completedSteps: Set<number>;
	visitedSteps: Set<number>;
};
const Stepper = ({
	currentStepNum,
	onClick,
	steps,
	completedSteps,
	visitedSteps,
}: StepperProps) => {
	return (
		<Card className="p-4 flex items-center justify-around">
			{steps.map((step, i) => {
				const isCurrentStep = currentStepNum === i;
				const isStepVisited = visitedSteps.has(i);
				const isStepComplete = completedSteps.has(i);

				return (
					<Step
						key={i}
						disabled={!isStepVisited}
						onClick={() => onClick({ stepName: step, stepNum: i })}
						number={i}
						isActive={isCurrentStep}
						isComplete={isStepComplete}
						name={step}
					/>
				);
			})}
		</Card>
	);
};

type StepProps = {
	isActive?: boolean;
	isComplete?: boolean;
	disabled?: boolean;
	number: number;
	name: string;
	onClick?: ({ number, name }: { number: number; name: string }) => void;
};

const Step = ({
	isActive = false,
	isComplete = false,
	disabled = false,
	onClick = () => {},
	/** Assume steps are indexed =0 */
	number,
	name,
}: StepProps) => {
	// add 1 to number assuming index 0
	const adjustedNumberDisplay = number + 1;
	const numberLabel =
		adjustedNumberDisplay < 10
			? `0${adjustedNumberDisplay}`
			: String(adjustedNumberDisplay);

	return (
		<button
			className={cn(
				"flex items-center gap-3",
				disabled && "cursor-not-allowed",
			)}
			disabled={disabled}
			onClick={() => onClick({ number, name })}
		>
			{isComplete ? (
				<Icon
					id="CircleCheck"
					color={isActive ? "teal" : "grey"}
					className="h-12 w-12"
				/>
			) : (
				<StepIcon isActive={isActive} label={numberLabel} />
			)}
			<Typography
				variant="bodyLarge"
				className={cn(
					"text-gray-500 border-gray-500",
					isActive && "text-teal-700 border-teal-700",
				)}
			>
				{name}
			</Typography>
		</button>
	);
};

type StepIconProps = {
	label: string;
	isActive?: boolean;
};
const StepIcon = ({ isActive = false, label }: StepIconProps) => (
	<div
		className={cn(
			"flex items-center justify-center w-12 h-12 rounded-full border-4 text-gray-500 border-gray-500",
			isActive && "text-teal-700 border-teal-700",
		)}
	>
		<Typography
			variant="bodyLarge"
			className={cn(
				"text-gray-500 border-gray-500",
				isActive && "text-teal-700 border-teal-700",
			)}
		>
			{label}
		</Typography>
	</div>
);

export { Step, Stepper };
