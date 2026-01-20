import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { type ColorMode, useColorMode } from "@/hooks/use-color-mode";
import { capitalize } from "@/utils";

const STATE_TYPES = [
	"completed",
	"running",
	"scheduled",
	"pending",
	"failed",
	"cancelled",
	"cancelling",
	"crashed",
	"paused",
] as const;

type StateType = (typeof STATE_TYPES)[number];

function getColorModeClass(mode: ColorMode): string {
	return `color-mode-${mode}`;
}

type ColorModeOptionProps = {
	mode: ColorMode;
};

const ColorModeOption = ({ mode }: ColorModeOptionProps) => {
	return (
		<div
			className={`flex items-center justify-between gap-2 w-full ${getColorModeClass(mode)}`}
		>
			<span>{capitalize(mode)}</span>
			<div className="flex items-center gap-1">
				{STATE_TYPES.map((state) => (
					<StateColorCircle key={state} state={state} />
				))}
			</div>
		</div>
	);
};

type StateColorCircleProps = {
	state: StateType;
};

const StateColorCircle = ({ state }: StateColorCircleProps) => {
	const stateColorMap: Record<StateType, string> = {
		completed: "bg-[var(--state-completed-500)]",
		running: "bg-[var(--state-running-500)]",
		scheduled: "bg-[var(--state-scheduled-500)]",
		pending: "bg-[var(--state-pending-500)]",
		failed: "bg-[var(--state-failed-500)]",
		cancelled: "bg-[var(--state-cancelled-500)]",
		cancelling: "bg-[var(--state-cancelling-500)]",
		crashed: "bg-[var(--state-crashed-500)]",
		paused: "bg-[var(--state-paused-500)]",
	};

	return <span className={`w-4 h-4 rounded-full ${stateColorMap[state]}`} />;
};

export const ColorModeSelect = () => {
	const { colorMode, setColorMode, colorModes } = useColorMode();

	return (
		<div className="flex flex-col gap-1">
			<label htmlFor="color-mode-select">Color Mode</label>
			<Select
				value={colorMode}
				onValueChange={(value: ColorMode) => setColorMode(value)}
			>
				<SelectTrigger className="w-96" id="color-mode-select">
					<SelectValue placeholder="Select a color mode">
						<ColorModeOption mode={colorMode} />
					</SelectValue>
				</SelectTrigger>
				<SelectContent>
					<SelectGroup>
						{colorModes.map((mode) => (
							<SelectItem key={mode} value={mode}>
								<ColorModeOption mode={mode} />
							</SelectItem>
						))}
					</SelectGroup>
				</SelectContent>
			</Select>
		</div>
	);
};
