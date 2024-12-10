// Centralize testing utilities to be imported in this file

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

/**
 * Wraps render() components with app-wide providers
 *
 * @example
 * import { createWrapper } from '@tests/utils'
 *
 * ```tsx
 *	const result = render(<MyComponentToTest />, {
 *		wrapper: createWrapper(),
 *	});
 * ```
 */
export const createWrapper = ({ queryClient = new QueryClient() } = {}) => {
	const Wrapper = ({ children }: { children: React.ReactNode }) => (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);
	return Wrapper;
};
