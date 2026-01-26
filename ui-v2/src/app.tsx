import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { RouterProvider } from "@tanstack/react-router";
import { AnalyticsProvider } from "@/analytics/analytics-provider";
import { AuthProvider, useAuth } from "@/auth";
import { queryClient, router } from "./router";

const showDevtools = import.meta.env.VITE_DISABLE_DEVTOOLS !== "true";

function InnerApp() {
	const auth = useAuth();
	return <RouterProvider router={router} context={{ queryClient, auth }} />;
}

export const App = () => {
	return (
		<QueryClientProvider client={queryClient}>
			<AnalyticsProvider>
				<AuthProvider>
					<InnerApp />
				</AuthProvider>
			</AnalyticsProvider>
			{showDevtools && <ReactQueryDevtools />}
		</QueryClientProvider>
	);
};
