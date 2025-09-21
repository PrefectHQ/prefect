import { format, formatDistanceToNow, isValid, parseISO } from "date-fns";

import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/utils";

type FormattedDateProps = {
	date: string | Date | null | undefined;
	format?: "relative" | "absolute" | "both";
	showTooltip?: boolean;
	className?: string;
};

export const FormattedDate = ({
	date,
	format: formatType = "relative",
	showTooltip = true,
	className,
}: FormattedDateProps) => {
	// Handle null/undefined dates
	if (!date) {
		return (
			<span className={cn("text-muted-foreground", className)}>Never</span>
		);
	}

	// Parse the date
	let parsedDate: Date;
	try {
		parsedDate = typeof date === "string" ? parseISO(date) : date;
		if (!isValid(parsedDate)) {
			return (
				<span className={cn("text-muted-foreground", className)}>
					Invalid date
				</span>
			);
		}
	} catch {
		return (
			<span className={cn("text-muted-foreground", className)}>
				Invalid date
			</span>
		);
	}

	// Format the date based on the type
	const getFormattedText = () => {
		switch (formatType) {
			case "relative":
				return formatDistanceToNow(parsedDate, { addSuffix: true });
			case "absolute":
				return format(parsedDate, "MMM d, yyyy 'at' h:mm a");
			case "both":
				return formatDistanceToNow(parsedDate, { addSuffix: true });
			default:
				return formatDistanceToNow(parsedDate, { addSuffix: true });
		}
	};

	const formattedText = getFormattedText();
	const absoluteText = format(parsedDate, "MMMM d, yyyy 'at' h:mm:ss a");

	const dateElement = <span className={className}>{formattedText}</span>;

	// Show tooltip for relative dates or when explicitly requested
	if (showTooltip && (formatType === "relative" || formatType === "both")) {
		return (
			<TooltipProvider>
				<Tooltip>
					<TooltipTrigger asChild>{dateElement}</TooltipTrigger>
					<TooltipContent>
						<p>{absoluteText}</p>
					</TooltipContent>
				</Tooltip>
			</TooltipProvider>
		);
	}

	return dateElement;
};
