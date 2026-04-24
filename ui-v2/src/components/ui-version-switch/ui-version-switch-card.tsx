import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";

type UiVersionSwitchCardProps = {
	onSwitch: () => void;
};

export const UiVersionSwitchCard = ({ onSwitch }: UiVersionSwitchCardProps) => {
	return (
		<Card>
			<CardHeader>
				<CardTitle>UI Version</CardTitle>
				<CardDescription>
					Switch this browser back to the V1 UI and share feedback about what is
					not working for you in V2.
				</CardDescription>
			</CardHeader>
			<CardContent className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
				<div className="text-sm text-muted-foreground">
					Your choice is saved in this browser so future visits open the same UI
					first.
				</div>
				<Button onClick={onSwitch}>Switch to V1</Button>
			</CardContent>
		</Card>
	);
};
