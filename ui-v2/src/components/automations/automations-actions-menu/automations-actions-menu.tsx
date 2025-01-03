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
import { useToast } from "@/hooks/use-toast";
import { Link } from "@tanstack/react-router";

type Props = {
	id: string;
	onDelete: () => void;
};

export const AutomationsActionsMenu = ({ id, onDelete }: Props) => {
	const { toast } = useToast();

	const handleCopyId = (id: string) => {
		void navigator.clipboard.writeText(id);
		toast({ title: "ID copied" });
	};

	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button variant="outline" className="h-8 w-8 p-0">
					<span className="sr-only">Open menu</span>
					<Icon id="MoreVertical" className="h-4 w-4" />
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
						Documentation <Icon id="ExternalLink" className="ml-2 h-4 w-4" />
					</a>
				</DropdownMenuItem>
			</DropdownMenuContent>
		</DropdownMenu>
	);
};
