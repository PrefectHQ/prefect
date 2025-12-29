import { Typography } from "@/components/ui/typography";

type InferredFlowRunActionDescriptionProps = {
	action: "resume" | "cancel" | "suspend";
};

const ACTION_LABELS = {
	resume: "Resume",
	cancel: "Cancel",
	suspend: "Suspend",
} as const;

export const InferredFlowRunActionDescription = ({
	action,
}: InferredFlowRunActionDescriptionProps) => {
	return (
		<Typography variant="bodySmall" className="text-muted-foreground">
			{ACTION_LABELS[action]} a flow run inferred from the triggering event
		</Typography>
	);
};
