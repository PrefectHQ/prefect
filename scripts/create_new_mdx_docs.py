import os
import subprocess


def run_command_for_modules(base_path, command_template, output_dir):
    # List all directories in the base path
    for module_name in os.listdir(base_path):
        module_path = os.path.join(base_path, module_name)
        # Check if the path is a directory
        if os.path.isdir(module_path):
            # Format the command with the module name and output directory
            command = command_template.format(module=module_name, output_dir=output_dir)
            # Execute the command
            subprocess.run(command, shell=True)
            print(f"Executed command for module: {module_name}")

            # Convert the generated .md file to .mdx
            md_file = os.path.join(output_dir, f"{module_name}.md")
            mdx_file = os.path.join(output_dir, f"{module_name}.mdx")
            if os.path.exists(md_file):
                convert_md_to_mdx(md_file, mdx_file)
                print(f"Converted {md_file} to {mdx_file}")


def convert_md_to_mdx(input_file, output_file):
    # Assuming md_to_mdx.py is in the same directory and has a function convert_md_to_mdx
    import md_to_mdx

    md_to_mdx.convert_md_to_mdx(input_file, output_file)


if __name__ == "__main__":
    # Base path for the integrations
    integrations_path = "../src/integrations"
    # Directory where the .md files are generated
    output_dir = "../docs/v3/api-ref/python"
    # Command template
    command_template = "uv run -m python_docstring_markdown ../src/{module}/{module} {output_dir}/{module}.md"
    # Run the command for each module and convert to .mdx
    run_command_for_modules(integrations_path, command_template, output_dir)
