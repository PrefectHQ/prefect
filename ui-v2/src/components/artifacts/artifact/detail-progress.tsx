export type DetailProgressProps = {
	progress: number;
};

export const DetailProgress = ({ progress }: DetailProgressProps) => {
	return (
		<p data-testid="progress-display" className="text-lg">
			Progress: {progress}%
		</p>
	);
};
