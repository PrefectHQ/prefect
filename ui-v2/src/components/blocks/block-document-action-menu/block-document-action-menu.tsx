import { Link } from "@tanstack/react-router";
import { toast } from "sonner";
import type { BlockDocument } from "@/api/block-documents";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";

export type BlockDocumentActionMenuProps = {
	blockDocument: BlockDocument;
	onDelete: () => void;
};

export const BlockDocumentActionMenu = ({
	blockDocument,
	onDelete,
}: BlockDocumentActionMenuProps) => {
	const handleCopyName = (_name: string) => {
		void navigator.clipboard.writeText(_name);
		toast.success("Copied to clipboard!");
	};

	const { id, name } = blockDocument;

	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button variant="outline" className="size-8 p-0">
					<span className="sr-only">Open menu</span>
					<Icon id="MoreVertical" className="size-4" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="end">
				<DropdownMenuLabel>Actions</DropdownMenuLabel>
				{name && (
					<DropdownMenuItem onClick={() => handleCopyName(name)}>
						Copy Name
					</DropdownMenuItem>
				)}
				<Link to="/blocks/block/$id/edit" params={{ id }}>
					<DropdownMenuItem>Edit</DropdownMenuItem>
				</Link>
				<DropdownMenuItem onClick={onDelete}>Delete</DropdownMenuItem>
			</DropdownMenuContent>
		</DropdownMenu>
	);
};
