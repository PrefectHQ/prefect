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

export type DeleteConfirmationDialogProps = {
	isOpen: boolean;
	title: string;
	description: string;
	onConfirm: () => void;
	onClose: () => void;
};

export const DeleteConfirmationDialog = ({
	isOpen,
	title,
	description,
	onConfirm,
	onClose,
}: DeleteConfirmationDialogProps) => (
	<AlertDialog open={isOpen} onOpenChange={onClose}>
		<AlertDialogContent>
			<AlertDialogHeader>
				<AlertDialogTitle>{title}</AlertDialogTitle>
				<AlertDialogDescription>{description}</AlertDialogDescription>
			</AlertDialogHeader>
			<AlertDialogFooter>
				<AlertDialogCancel onClick={onClose}>Cancel</AlertDialogCancel>
				<AlertDialogAction
					variant="destructive"
					onClick={() => {
						onConfirm();
						onClose();
					}}
				>
					Delete
				</AlertDialogAction>
			</AlertDialogFooter>
		</AlertDialogContent>
	</AlertDialog>
);
