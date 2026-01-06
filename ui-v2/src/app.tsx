import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { RouterProvider } from "@tanstack/react-router";
import { AppErrorBoundary } from "@/components/app-error-boundary";
import { queryClient, router } from "./router";

export const App = () => {
	return (
		<AppErrorBoundary>
			<QueryClientProvider client={queryClient}>
				<RouterProvider router={router} />
				<ReactQueryDevtools />
			</QueryClientProvider>
		</AppErrorBoundary>
	);
};
