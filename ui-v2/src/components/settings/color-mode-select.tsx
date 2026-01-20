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
					<SelectValue placeholder="Select a color mode" />
				</SelectTrigger>
				<SelectContent>
					<SelectGroup>
						{colorModes.map((mode) => (
							<SelectItem key={mode} value={mode}>
								{capitalize(mode)}
							</SelectItem>
						))}
					</SelectGroup>
				</SelectContent>
			</Select>
		</div>
	);
};
