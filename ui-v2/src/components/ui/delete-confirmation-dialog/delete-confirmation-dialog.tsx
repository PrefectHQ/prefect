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

type DeleteConfirmationDialogProps = {
	isOpen: boolean;
	title: string;
	description: string;
	itemName: string;
	onConfirm: () => void;
	onClose: () => void;
};

export const DeleteConfirmationDialog = ({
	isOpen,
	title,
	description,
	itemName,
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
					Delete {itemName}
				</AlertDialogAction>
			</AlertDialogFooter>
		</AlertDialogContent>
	</AlertDialog>
);
