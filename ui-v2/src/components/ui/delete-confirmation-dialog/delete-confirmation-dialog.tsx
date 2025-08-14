import { useState } from "react";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export type DeleteConfirmationDialogProps = {
	isOpen: boolean;
	title: string;
	description: string;
	onConfirm: () => void;
	onClose: () => void;
	confirmText?: string;
	isLoading?: boolean;
	loadingText?: string;
};

export const DeleteConfirmationDialog = ({
	isOpen,
	title,
	description,
	onConfirm,
	onClose,
	confirmText,
	isLoading = false,
	loadingText = "Deleting...",
}: DeleteConfirmationDialogProps) => {
	const [inputValue, setInputValue] = useState("");

	const handleClose = () => {
		setInputValue("");
		onClose();
	};

	const handleConfirm = () => {
		onConfirm();
		setInputValue("");
	};

	const isConfirmDisabled =
		isLoading || (!!confirmText && inputValue !== confirmText);

	return (
		<AlertDialog open={isOpen} onOpenChange={handleClose}>
			<AlertDialogContent>
				<AlertDialogHeader>
					<AlertDialogTitle>{title}</AlertDialogTitle>
					<AlertDialogDescription>{description}</AlertDialogDescription>
				</AlertDialogHeader>
				{confirmText && (
					<div className="space-y-2">
						<Label htmlFor="confirm-text">
							Type <strong>{confirmText}</strong> to confirm:
						</Label>
						<Input
							id="confirm-text"
							value={inputValue}
							onChange={(e) => setInputValue(e.target.value)}
							placeholder={confirmText}
						/>
					</div>
				)}
				<AlertDialogFooter>
					<AlertDialogCancel onClick={handleClose}>Cancel</AlertDialogCancel>
					<AlertDialogAction
						variant="destructive"
						onClick={handleConfirm}
						disabled={isConfirmDisabled}
					>
						{isLoading ? loadingText : "Delete"}
					</AlertDialogAction>
				</AlertDialogFooter>
			</AlertDialogContent>
		</AlertDialog>
	);
};
