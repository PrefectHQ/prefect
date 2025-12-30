import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";

export { buildApiUrl } from "./handlers";
export { server } from "./node";

/* Wraps render() components with app-wide providers
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
const createTestQueryClient = () =>
	new QueryClient({
		defaultOptions: {
			queries: { retry: false },
			mutations: { retry: false },
		},
	});

export const createWrapper = ({
	queryClient = createTestQueryClient(),
} = {}) => {
	// Written with createElement because our current vite config doesn't support jsx in tests/
	const Wrapper = ({ children }: { children: React.ReactNode }) =>
		createElement(QueryClientProvider, { client: queryClient }, children);
	return Wrapper;
};
