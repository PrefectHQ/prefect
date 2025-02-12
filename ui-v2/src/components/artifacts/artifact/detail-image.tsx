import { Typography } from "@/components/ui/typography";

export type DetailImageProps = {
	url: string;
};

export const DetailImage = ({ url }: DetailImageProps) => {
	return (
		<div data-testid={url} className="prose mt-2">
			<img
				data-testid={`image-${url}`}
				src={url}
				alt="artifact-image"
				className="w-full"
			/>

			<Typography variant="bodyLarge">
				Image URL:{" "}
				<a
					className="text-blue-700 hover:underline"
					target="_blank"
					href={url}
					rel="noreferrer"
				>
					{url}
				</a>
			</Typography>
		</div>
	);
};
