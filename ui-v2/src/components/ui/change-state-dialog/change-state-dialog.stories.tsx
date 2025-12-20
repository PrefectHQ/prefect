import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { StateBadge } from "@/components/ui/state-badge";
import { toastDecorator } from "@/storybook/utils";
import { ChangeStateDialog, useChangeStateDialog } from "./index";

const meta: Meta<typeof ChangeStateDialog> = {
	title: "UI/ChangeStateDialog",
	component: ChangeStateDialog,
	parameters: {
		layout: "centered",
	},
	decorators: [toastDecorator],
};

export default meta;
type Story = StoryObj<typeof ChangeStateDialog>;

const InteractiveDemo = () => {
	const { open, onOpenChange, openDialog } = useChangeStateDialog();
	const [isLoading, setIsLoading] = useState(false);

	const handleConfirm = (newState: { type: string; message?: string }) => {
		setIsLoading(true);
		setTimeout(() => {
			setIsLoading(false);
			onOpenChange(false);
			toast.success(
				<div className="flex items-center gap-2">
					Task run state changed to{" "}
					<StateBadge
						type={
							newState.type as "COMPLETED" | "FAILED" | "CANCELLED" | "CRASHED"
						}
						name={newState.type}
					/>
				</div>,
			);
		}, 1000);
	};

	return (
		<div>
			<Button onClick={openDialog}>Change Task Run State</Button>
			<ChangeStateDialog
				open={open}
				onOpenChange={onOpenChange}
				currentState={{ type: "RUNNING", name: "Running" }}
				label="Task Run"
				onConfirm={handleConfirm}
				isLoading={isLoading}
			/>
		</div>
	);
};

export const Default: Story = {
	render: () => <InteractiveDemo />,
	args: {
		open: true,
		currentState: { type: "RUNNING", name: "Running" },
		label: "Task Run",
	},
};

export const WithCurrentState: Story = {
	args: {
		open: true,
		currentState: { type: "RUNNING", name: "Running" },
		label: "Task Run",
		onConfirm: (newState: { type: string; message?: string }) => {
			toast.success(
				<div className="flex items-center gap-2">
					State changed to{" "}
					<StateBadge
						type={
							newState.type as "COMPLETED" | "FAILED" | "CANCELLED" | "CRASHED"
						}
						name={newState.type}
					/>
				</div>,
			);
		},
	},
};

export const WithoutCurrentState: Story = {
	args: {
		open: true,
		currentState: null,
		label: "Task Run",
		onConfirm: (newState: { type: string; message?: string }) => {
			toast.success(`State changed to ${newState.type}`);
		},
	},
};

export const Loading: Story = {
	args: {
		open: true,
		currentState: { type: "RUNNING", name: "Running" },
		label: "Task Run",
		isLoading: true,
	},
};

export const FlowRunLabel: Story = {
	args: {
		open: true,
		currentState: { type: "PENDING", name: "Pending" },
		label: "Flow Run",
		onConfirm: (newState: { type: string; message?: string }) => {
			toast.success(
				<div className="flex items-center gap-2">
					Flow run state changed to{" "}
					<StateBadge
						type={
							newState.type as "COMPLETED" | "FAILED" | "CANCELLED" | "CRASHED"
						}
						name={newState.type}
					/>
				</div>,
			);
		},
	},
};
