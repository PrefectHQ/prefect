import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icons";
import { cn } from "@/utils";

type StepperProps = {
	currentStepNum: number;
	steps: Array<string> | ReadonlyArray<string>;
	onClick: ({
		stepName,
		stepNum,
	}: {
		stepName: string;
		stepNum: number;
	}) => void;
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
		<Card className="p-4 flex flex-row items-center justify-around gap-4 overflow-x-auto">
			{steps.map((step, i) => {
				const isCurrentStep = currentStepNum === i;
				const isStepVisited = visitedSteps.has(i);
				const isStepComplete = completedSteps.has(i);

				return (
					<Step
						key={step}
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
			type="button"
			className={cn(
				"flex items-center gap-3 text-nowrap",
				disabled && "cursor-not-allowed",
			)}
			disabled={disabled}
			onClick={() => onClick({ number, name })}
		>
			{isComplete ? (
				<Icon
					id="CircleCheck"
					color={isActive ? "teal" : "grey"}
					className="size-12"
				/>
			) : (
				<StepIcon isActive={isActive} label={numberLabel} />
			)}
			<p
				className={cn(
					"text-lg text-muted-foreground border-muted-foreground whitespace-nowrap",
					isActive && "text-teal-700 border-teal-700",
				)}
			>
				{name}
			</p>
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
			"flex items-center justify-center size-12 rounded-full border-4 text-muted-foreground border-muted-foreground",
			isActive && "text-teal-700 border-teal-700",
		)}
	>
		<p
			className={cn(
				"text-lg text-muted-foreground border-muted-foreground",
				isActive && "text-teal-700 border-teal-700",
			)}
		>
			{label}
		</p>
	</div>
);

export { Step, Stepper };
