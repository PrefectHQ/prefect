import type { ComponentProps } from "react";
import { lazy, Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";

const JsonInputLazy = lazy(() =>
	import("./json-input").then((mod) => ({ default: mod.JsonInput })),
);

type LazyJsonInputProps = ComponentProps<typeof JsonInputLazy>;

export function LazyJsonInput({ className, ...props }: LazyJsonInputProps) {
	return (
		<Suspense
			fallback={<Skeleton className={`min-h-[200px] ${className ?? ""}`} />}
		>
			<JsonInputLazy className={className} {...props} />
		</Suspense>
	);
}
