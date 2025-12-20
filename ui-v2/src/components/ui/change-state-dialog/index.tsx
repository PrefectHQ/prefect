import { useCallback, useEffect, useState } from "react";
import type { components } from "@/api/prefect";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { StateBadge } from "@/components/ui/state-badge";
import { StateSelect } from "@/components/ui/state-select";

type StateType = components["schemas"]["StateType"];

export type ChangeStateDialogProps = {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	currentState: { type: string; name: string } | null;
	label: string;
	onConfirm: (newState: { type: string; message?: string }) => void;
	isLoading?: boolean;
};

export const ChangeStateDialog = ({
	open,
	onOpenChange,
	currentState,
	label,
	onConfirm,
	isLoading = false,
}: ChangeStateDialogProps) => {
	const [selectedState, setSelectedState] = useState<StateType | undefined>(
		undefined,
	);
	const [message, setMessage] = useState("");

	useEffect(() => {
		if (!open) {
			setSelectedState(undefined);
			setMessage("");
		}
	}, [open]);

	const handleConfirm = () => {
		if (selectedState) {
			onConfirm({
				type: selectedState,
				message: message || undefined,
			});
		}
	};

	const isConfirmDisabled = !selectedState || isLoading;

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent aria-describedby={undefined}>
				<DialogHeader>
					<DialogTitle>Change {label} State</DialogTitle>
				</DialogHeader>

				<div className="space-y-4">
					{currentState && (
						<div>
							<Label className="mb-2 block">Current State</Label>
							<StateBadge
								type={currentState.type as StateType}
								name={currentState.name}
							/>
						</div>
					)}

					<div>
						<Label htmlFor="desired-state" className="mb-2 block">
							Desired State
						</Label>
						<StateSelect
							value={selectedState}
							onValueChange={setSelectedState}
							terminalOnly
						/>
					</div>

					<div>
						<Label htmlFor="message" className="mb-2 block">
							Reason (Optional)
						</Label>
						<Input
							id="message"
							value={message}
							onChange={(e) => setMessage(e.target.value)}
							placeholder="State changed manually via UI"
						/>
					</div>
				</div>

				<DialogFooter>
					<Button
						type="button"
						variant="outline"
						onClick={() => onOpenChange(false)}
						disabled={isLoading}
					>
						Close
					</Button>
					<Button
						type="button"
						onClick={handleConfirm}
						disabled={isConfirmDisabled}
						loading={isLoading}
					>
						Change
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
};

export type UseChangeStateDialogResult = {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	openDialog: () => void;
	closeDialog: () => void;
};

export const useChangeStateDialog = (): UseChangeStateDialogResult => {
	const [open, setOpen] = useState(false);

	const openDialog = useCallback(() => setOpen(true), []);
	const closeDialog = useCallback(() => setOpen(false), []);

	return {
		open,
		onOpenChange: setOpen,
		openDialog,
		closeDialog,
	};
};
