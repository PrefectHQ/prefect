import { type QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { RouterProvider } from "@tanstack/react-router";
import { AnalyticsProvider } from "@/analytics/analytics-provider";
import { AuthProvider, useAuth } from "@/auth";
import { queryClient, router } from "./router";

const showDevtools = import.meta.env.VITE_DISABLE_DEVTOOLS !== "true";

function InnerApp({
	appRouter,
	appQueryClient,
}: {
	appRouter: typeof router;
	appQueryClient: QueryClient;
}) {
	const auth = useAuth();
	return (
		<RouterProvider
			router={appRouter}
			context={{ queryClient: appQueryClient, auth }}
		/>
	);
}

export const App = ({
	appRouter = router,
	appQueryClient = queryClient,
}: {
	appRouter?: typeof router;
	appQueryClient?: QueryClient;
}) => {
	return (
		<QueryClientProvider client={appQueryClient}>
			<AnalyticsProvider>
				<AuthProvider>
					<InnerApp appRouter={appRouter} appQueryClient={appQueryClient} />
				</AuthProvider>
			</AnalyticsProvider>
			{showDevtools && <ReactQueryDevtools />}
		</QueryClientProvider>
	);
};
