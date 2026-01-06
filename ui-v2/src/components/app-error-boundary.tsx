import { Component, type ReactNode } from "react";
import { categorizeError, type ServerError } from "@/api/error-utils";
import { ServerErrorDisplay } from "@/components/ui/server-error";

type AppErrorBoundaryProps = {
	children: ReactNode;
};

type AppErrorBoundaryState = {
	hasError: boolean;
	error: ServerError | null;
};

export class AppErrorBoundary extends Component<
	AppErrorBoundaryProps,
	AppErrorBoundaryState
> {
	constructor(props: AppErrorBoundaryProps) {
		super(props);
		this.state = { hasError: false, error: null };
	}

	static getDerivedStateFromError(error: Error): AppErrorBoundaryState {
		const serverError = categorizeError(
			error,
			"Failed to initialize application",
		);
		return { hasError: true, error: serverError };
	}

	componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
		// Log error for debugging
		console.error("App error boundary caught error:", error, errorInfo);
	}

	handleRetry = () => {
		// Reset error state to trigger re-render
		this.setState({ hasError: false, error: null });
	};

	render() {
		if (this.state.hasError && this.state.error) {
			return (
				<ServerErrorDisplay
					error={this.state.error}
					onRetry={this.handleRetry}
				/>
			);
		}

		return this.props.children;
	}
}
