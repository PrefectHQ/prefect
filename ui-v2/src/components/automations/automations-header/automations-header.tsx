import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import { Typography } from "@/components/ui/typography";
import { Link } from "@tanstack/react-router";

export const AutomationsHeader = () => {
	return (
		<div className="flex items-center gap-2">
			<Typography variant="h4">Automations</Typography>
			<Button size="icon" className="h-7 w-7" variant="outline">
				<Link to="/automations/create">
					<Icon id="Plus" className="h-4 w-4" />
				</Link>
			</Button>
		</div>
	);
};
