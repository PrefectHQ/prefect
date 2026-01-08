import type { ComponentProps } from "react";
import { lazy, Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";

const PythonInputLazy = lazy(() =>
	import("./python-input").then((mod) => ({ default: mod.PythonInput })),
);

type LazyPythonInputProps = ComponentProps<typeof PythonInputLazy>;

export function LazyPythonInput({ className, ...props }: LazyPythonInputProps) {
	return (
		<Suspense
			fallback={<Skeleton className={`min-h-[200px] ${className ?? ""}`} />}
		>
			<PythonInputLazy className={className} {...props} />
		</Suspense>
	);
}
