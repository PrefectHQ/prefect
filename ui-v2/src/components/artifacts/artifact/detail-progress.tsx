import { Typography } from "@/components/ui/typography";

export type DetailProgressProps = {
	progress: number;
};

export const DetailProgress = ({ progress }: DetailProgressProps) => {
	return (
		<Typography data-testid="progress-display" variant="bodyLarge">
			Progress: {progress}%
		</Typography>
	);
};
