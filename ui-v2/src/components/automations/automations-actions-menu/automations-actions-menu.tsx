import { Link } from "@tanstack/react-router";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { DOCS_LINKS } from "@/components/ui/docs-link";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";

type Props = {
	id: string;
	onDelete: () => void;
};

export const AutomationsActionsMenu = ({ id, onDelete }: Props) => {
	const handleCopyId = (id: string) => {
		void navigator.clipboard.writeText(id);
		toast.success("ID copied");
	};

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
				<DropdownMenuItem onClick={() => handleCopyId(id)}>
					Copy ID
				</DropdownMenuItem>
				<DropdownMenuItem>
					<Link to="/automations/automation/$id/edit" params={{ id }}>
						Edit
					</Link>
				</DropdownMenuItem>
				<DropdownMenuItem onClick={onDelete}>Delete</DropdownMenuItem>
				<DropdownMenuItem>
					<a
						href={DOCS_LINKS["automations-guide"]}
						className="flex items-center"
					>
						Documentation <Icon id="ExternalLink" className="ml-2 size-4" />
					</a>
				</DropdownMenuItem>
			</DropdownMenuContent>
		</DropdownMenu>
	);
};
