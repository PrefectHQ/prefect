import { Typography } from "@/components/ui/typography";

type FlowRunActionDescriptionProps = {
	action: "Suspend" | "Cancel" | "Resume";
};

export const FlowRunActionDescription = ({
	action,
}: FlowRunActionDescriptionProps) => {
	return (
		<Typography variant="bodySmall" className="text-muted-foreground">
			{action} flow run inferred from the triggering event
		</Typography>
	);
};
