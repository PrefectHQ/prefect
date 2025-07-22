import type { Meta, StoryObj } from "@storybook/react";
import { LogoImage } from "./logo-image";

const meta: Meta<typeof LogoImage> = {
	title: "UI/LogoImage",
	component: LogoImage,
	parameters: {
		layout: "centered",
	},
	tags: ["autodocs"],
	argTypes: {
		size: {
			control: { type: "select" },
			options: ["sm", "md", "lg"],
		},
	},
};

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	args: {
		url: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/docker/docker-original.svg",
		alt: "Docker",
		size: "md",
	},
};

export const Small: Story = {
	args: {
		url: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/kubernetes/kubernetes-plain.svg",
		alt: "Kubernetes",
		size: "sm",
	},
};

export const Large: Story = {
	args: {
		url: "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/amazonwebservices/amazonwebservices-original.svg",
		alt: "AWS",
		size: "lg",
	},
};

export const NoUrl: Story = {
	args: {
		url: null,
		alt: "Process",
		size: "md",
	},
};

export const AllSizes: Story = {
	render: () => (
		<div className="flex items-center gap-4">
			<LogoImage
				url="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/python/python-original.svg"
				alt="Python"
				size="sm"
			/>
			<LogoImage
				url="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/python/python-original.svg"
				alt="Python"
				size="md"
			/>
			<LogoImage
				url="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/python/python-original.svg"
				alt="Python"
				size="lg"
			/>
		</div>
	),
};
