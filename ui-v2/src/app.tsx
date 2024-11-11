import { RouterProvider } from "@tanstack/react-router";
import { queryClient, router } from "./router";
import { QueryClientProvider } from "@tanstack/react-query";

export const App = () => {
	return (
		<QueryClientProvider client={queryClient}>
			<RouterProvider router={router} />
		</QueryClientProvider>
	);
};
