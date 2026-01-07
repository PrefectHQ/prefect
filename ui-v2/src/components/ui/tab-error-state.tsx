import { AlertCircle, RefreshCw } from "lucide-react";
import type { ServerError } from "@/api/error-utils";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils";

type TabErrorStateProps = {
	error: ServerError;
	onRetry?: () => void;
	isRetrying?: boolean;
};

export function TabErrorState({
	error,
	onRetry,
	isRetrying,
}: TabErrorStateProps) {
	return (
		<div className="flex flex-col items-center justify-center py-8 text-center">
			<div className="rounded-full bg-destructive/10 p-2 mb-3">
				<AlertCircle className="size-6 text-destructive" />
			</div>
			<div className="space-y-1 mb-4">
				<p className="font-medium">{error.message}</p>
				{error.details && (
					<p className="text-xs text-muted-foreground max-w-sm">
						{error.details}
					</p>
				)}
			</div>
			{onRetry && (
				<Button
					variant="outline"
					size="sm"
					onClick={onRetry}
					disabled={isRetrying}
					className="gap-2"
				>
					<RefreshCw className={cn("size-3", isRetrying && "animate-spin")} />
					{isRetrying ? "Retrying..." : "Retry"}
				</Button>
			)}
		</div>
	);
}
