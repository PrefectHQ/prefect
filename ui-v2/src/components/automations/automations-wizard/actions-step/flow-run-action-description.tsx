type FlowRunActionDescriptionProps = {
	action: "Suspend" | "Cancel" | "Resume";
};

export const FlowRunActionDescription = ({
	action,
}: FlowRunActionDescriptionProps) => {
	// Vue uses different text for resume vs cancel/suspend:
	// - Cancel/Suspend: "{Action} flow run inferred from the triggering event"
	// - Resume: "Resume a flow run inferred from the triggering event"
	const text =
		action === "Resume"
			? "Resume a flow run inferred from the triggering event"
			: `${action} flow run inferred from the triggering event`;

	return <p className="text-sm text-muted-foreground">{text}</p>;
};
