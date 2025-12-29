import { Component, type ReactNode } from "react";

type ErrorBoundaryProps = {
	children: ReactNode;
	fallback: ReactNode | ((error: Error) => ReactNode);
};

type ErrorBoundaryState = {
	hasError: boolean;
	error: Error | null;
};

export class ErrorBoundary extends Component<
	ErrorBoundaryProps,
	ErrorBoundaryState
> {
	constructor(props: ErrorBoundaryProps) {
		super(props);
		this.state = { hasError: false, error: null };
	}

	static getDerivedStateFromError(error: Error): ErrorBoundaryState {
		return { hasError: true, error };
	}

	render() {
		if (this.state.hasError) {
			const { fallback } = this.props;
			if (typeof fallback === "function") {
				return fallback(this.state.error ?? new Error("Unknown error"));
			}
			return fallback;
		}
		return this.props.children;
	}
}
