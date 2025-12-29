import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

type TabErrorStateProps = {
	message?: string;
	onRetry?: () => void;
};

export function TabErrorState({
	message = "Failed to load content",
	onRetry,
}: TabErrorStateProps) {
	return (
		<div className="flex flex-col items-center justify-center py-8 text-center">
			<AlertCircle className="size-8 text-destructive mb-2" />
			<p className="text-sm text-muted-foreground mb-4">{message}</p>
			{onRetry && (
				<Button variant="outline" size="sm" onClick={onRetry}>
					Retry
				</Button>
			)}
		</div>
	);
}
