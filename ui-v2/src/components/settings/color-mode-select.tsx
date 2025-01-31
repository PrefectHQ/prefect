import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { useLocalStorage } from "@/hooks/use-local-storage";
import { capitalize } from "@/utils";

// TODO: Add colors in select content
const COLOR_MODES = [
	"default",
	"achromatopsia",
	"deuteranopia",
	"deuteranomaly",
	"protaponia",
	"protanomaly",
	"tritanomaly",
	"tritanopia",
] as const;
type ColorMode = (typeof COLOR_MODES)[number];

export const ColorModeSelect = () => {
	const [selectedColorMode, setSelectedColorMode] = useLocalStorage<ColorMode>(
		"prefect-color-mode",
		"default",
	);
	return (
		<div className="flex flex-col gap-1">
			<label htmlFor="color-mode-select">Color Mode</label>
			<Select
				value={selectedColorMode}
				onValueChange={(colorMode: ColorMode) =>
					setSelectedColorMode(colorMode)
				}
			>
				<SelectTrigger className="w-96" id="color-mode-select">
					<SelectValue placeholder="Select a color mode" />
				</SelectTrigger>
				<SelectContent>
					<SelectGroup>
						{COLOR_MODES.map((colorMode) => (
							<SelectItem key={colorMode} value={colorMode}>
								{capitalize(colorMode)}
							</SelectItem>
						))}
					</SelectGroup>
				</SelectContent>
			</Select>
		</div>
	);
};
