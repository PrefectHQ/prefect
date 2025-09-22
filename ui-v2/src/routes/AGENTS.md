# Routes Directory

This directory contains route definitions using Tanstack Router.

## Tanstack Router Guidelines

- Use `createFileRoute` for defining routes
- In routes, await for critical data and prefetch slow/deferred data
- Use `wrapInSuspense: true` for routes that use suspense queries

## Data Loading Pattern

```ts
export const Route = createFileRoute("/path")({
	component: RouteComponent,
	loader: async ({ params, context: { queryClient } }) => {
		// Non-dependent deferred data (prefetch)
		void queryClient.prefetchQuery(buildSomeQuery());

		// Critical data (await)
		const criticalData = await queryClient.ensureQueryData(
			buildCriticalQuery(params.id),
		);

		// Dependent deferred data (prefetch based on critical data)
		void queryClient.prefetchQuery(buildDependentQuery(criticalData.id));
	},
	wrapInSuspense: true,
});
```

## Best Practices

- Explicitly mark promises as ignored with the `void` operator when prefetching
- Use `ensureQueryData` for critical data that must be available before rendering
- Use `prefetchQuery` for data that can be loaded in the background
- Structure loader to prefetch non-dependent data first, then await critical data, then prefetch dependent data