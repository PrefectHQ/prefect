import { useCallback, useEffect, useRef, useState } from "react";
import type { ServerError, ServerErrorType } from "@/api/error-utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Icon, type IconId } from "@/components/ui/icons";

const BASE_RETRY_INTERVAL_MS = 5000;
const MAX_RETRY_INTERVAL_MS = 60000;

function getRetryInterval(attempt: number): number {
	const interval = BASE_RETRY_INTERVAL_MS * 2 ** attempt;
	return Math.min(interval, MAX_RETRY_INTERVAL_MS);
}

type ServerErrorDisplayProps = {
	error: ServerError;
	onRetry: () => void;
};

function getErrorIcon(type: ServerErrorType): IconId {
	switch (type) {
		case "network-error":
			return "ServerCrash";
		case "server-error":
			return "Server";
		case "client-error":
			return "Ban";
		default:
			return "Server";
	}
}

function getErrorColor(type: ServerErrorType): string {
	switch (type) {
		case "network-error":
			return "text-orange-500";
		case "server-error":
			return "text-red-500";
		case "client-error":
			return "text-yellow-500";
		default:
			return "text-muted-foreground";
	}
}

export function ServerErrorDisplay({
	error,
	onRetry,
}: ServerErrorDisplayProps) {
	const retryAttemptRef = useRef(0);
	const [secondsUntilRetry, setSecondsUntilRetry] = useState(
		getRetryInterval(0) / 1000,
	);
	const [isRetrying, setIsRetrying] = useState(false);

	const handleAutoRetry = useCallback(() => {
		setIsRetrying(true);
		onRetry();
		// Increment attempt for next auto-retry (exponential backoff)
		retryAttemptRef.current += 1;
		const nextInterval = getRetryInterval(retryAttemptRef.current);
		setSecondsUntilRetry(nextInterval / 1000);
		// Reset spinner after a brief delay
		setTimeout(() => setIsRetrying(false), 500);
	}, [onRetry]);

	const handleManualRetry = useCallback(() => {
		setIsRetrying(true);
		onRetry();
		// Reset attempt counter on manual retry
		retryAttemptRef.current = 0;
		setSecondsUntilRetry(getRetryInterval(0) / 1000);
		// Reset spinner after a brief delay
		setTimeout(() => setIsRetrying(false), 500);
	}, [onRetry]);

	// Automatic retry countdown with exponential backoff
	useEffect(() => {
		const interval = setInterval(() => {
			setSecondsUntilRetry((prev) => {
				if (prev <= 1) {
					handleAutoRetry();
					return prev; // Will be updated by handleAutoRetry
				}
				return prev - 1;
			});
		}, 1000);

		return () => clearInterval(interval);
	}, [handleAutoRetry]);

	const iconId = getErrorIcon(error.type);
	const iconColor = getErrorColor(error.type);

	return (
		<div className="flex min-h-screen items-center justify-center bg-background p-4">
			<Card className="w-full max-w-md">
				<CardContent className="flex flex-col items-center gap-6 pt-6 text-center">
					<div className={`rounded-full bg-muted p-4 ${iconColor}`}>
						<Icon id={iconId} className="size-12" />
					</div>

					<div className="space-y-2">
						<h1 className="text-2xl font-bold">{error.message}</h1>
						{error.details && (
							<p className="text-muted-foreground">{error.details}</p>
						)}
						{error.statusCode && (
							<p className="text-sm text-muted-foreground">
								Status code: {error.statusCode}
							</p>
						)}
					</div>

					<div className="flex flex-col items-center gap-3">
						<Button
							onClick={handleManualRetry}
							disabled={isRetrying}
							className="gap-2"
						>
							<Icon
								id="RefreshCw"
								className={`size-4 ${isRetrying ? "animate-spin" : ""}`}
							/>
							{isRetrying ? "Retrying..." : "Retry now"}
						</Button>

						<p className="text-sm text-muted-foreground">
							Automatically retrying in {secondsUntilRetry}s
						</p>
					</div>

					<div className="border-t pt-4 w-full">
						<p className="text-xs text-muted-foreground">
							Make sure the Prefect server is running:
						</p>
						<code className="mt-2 block rounded bg-muted px-3 py-2 text-xs">
							prefect server start
						</code>
					</div>
				</CardContent>
			</Card>
		</div>
	);
}
