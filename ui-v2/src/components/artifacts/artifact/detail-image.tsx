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

			<p className="text-lg">
				Image URL:{" "}
				<a
					className="text-link hover:text-link-hover hover:underline"
					target="_blank"
					href={url}
					rel="noreferrer"
				>
					{url}
				</a>
			</p>
		</div>
	);
};
