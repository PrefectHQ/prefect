import { Link } from "@tanstack/react-router";
import { toast } from "sonner";
import type { Event } from "@/api/events";
import { formatEventDate } from "@/components/automations/automations-wizard";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";

type EventActionMenuProps = {
	event: Event;
};

export function EventActionMenu({ event }: EventActionMenuProps) {
	const handleCopyId = () => {
		void navigator.clipboard.writeText(event.id);
		toast.success("ID copied");
	};

	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button
					variant="outline"
					className="size-8 p-0"
					aria-label="Event actions"
				>
					<span className="sr-only">Open menu</span>
					<Icon id="MoreVertical" className="size-4" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="end">
				<Link
					to="/automations/create"
					search={{
						eventId: event.id,
						eventDate: formatEventDate(event.occurred),
					}}
				>
					<DropdownMenuItem>
						<Icon id="Zap" className="mr-2 size-4" />
						Automate
					</DropdownMenuItem>
				</Link>
				<DropdownMenuItem onClick={handleCopyId}>
					<Icon id="Copy" className="mr-2 size-4" />
					Copy ID
				</DropdownMenuItem>
			</DropdownMenuContent>
		</DropdownMenu>
	);
}
