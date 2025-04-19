import { Skeleton } from "@/components/ui/skeleton";

const DEFAULT_NUM_SKELETONS = 4;

type LoadingSelectStateProps = {
	length?: number;
};

export const LoadingSelectState = ({
	length = DEFAULT_NUM_SKELETONS,
}: LoadingSelectStateProps) =>
	Array.from({ length }, (_, index) => (
		// biome-ignore lint/suspicious/noArrayIndexKey: ok for loading skeletons
		<Skeleton key={index} className="mt-2 p-4 h-2 w-full" />
	));
