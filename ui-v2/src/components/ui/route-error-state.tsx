import { AlertCircle, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ServerError } from "@/api/error-utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/utils";

const BASE_RETRY_INTERVAL_MS = 5000;
const MAX_RETRY_INTERVAL_MS = 30000;

function getRetryInterval(attempt: number): number {
	const interval = BASE_RETRY_INTERVAL_MS * 2 ** attempt;
	return Math.min(interval, MAX_RETRY_INTERVAL_MS);
}

type RouteErrorStateProps = {
	error: ServerError;
	onRetry: () => void;
};

export function RouteErrorState({ error, onRetry }: RouteErrorStateProps) {
	const retryAttemptRef = useRef(0);
	const [secondsUntilRetry, setSecondsUntilRetry] = useState(
		getRetryInterval(0) / 1000,
	);
	const [isRetrying, setIsRetrying] = useState(false);

	const handleAutoRetry = useCallback(() => {
		setIsRetrying(true);
		onRetry();
		retryAttemptRef.current += 1;
		const nextInterval = getRetryInterval(retryAttemptRef.current);
		setSecondsUntilRetry(nextInterval / 1000);
		setTimeout(() => setIsRetrying(false), 500);
	}, [onRetry]);

	const handleManualRetry = useCallback(() => {
		setIsRetrying(true);
		onRetry();
		retryAttemptRef.current = 0;
		setSecondsUntilRetry(getRetryInterval(0) / 1000);
		setTimeout(() => setIsRetrying(false), 500);
	}, [onRetry]);

	useEffect(() => {
		const interval = setInterval(() => {
			setSecondsUntilRetry((prev) => {
				if (prev <= 1) {
					handleAutoRetry();
					return prev;
				}
				return prev - 1;
			});
		}, 1000);

		return () => clearInterval(interval);
	}, [handleAutoRetry]);

	return (
		<Card className="mx-auto max-w-md">
			<CardContent className="flex flex-col items-center gap-4 pt-6 text-center">
				<div className="rounded-full bg-destructive/10 p-3">
					<AlertCircle className="size-8 text-destructive" />
				</div>

				<div className="space-y-1">
					<h2 className="text-lg font-semibold">{error.message}</h2>
					{error.details && (
						<p className="text-sm text-muted-foreground">{error.details}</p>
					)}
				</div>

				<div className="flex flex-col items-center gap-2">
					<Button
						onClick={handleManualRetry}
						disabled={isRetrying}
						variant="outline"
						className="gap-2"
					>
						<RefreshCw className={cn("size-4", isRetrying && "animate-spin")} />
						{isRetrying ? "Retrying..." : "Retry"}
					</Button>

					<p className="text-xs text-muted-foreground">
						Retrying in {secondsUntilRetry}s
					</p>
				</div>
			</CardContent>
		</Card>
	);
}
