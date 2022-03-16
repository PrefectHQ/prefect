##
## THIS FILE WAS COPIED FROM https://github.com/bharel/mkdocs-render-swagger-plugin/blob/main/render_swagger.py
## TO ALLOW FOR CUSTOM MODIFICATION TO THE SWAGGERUIBUNDLE OBJECT
##

import os
import re
import string
import urllib.parse
from pathlib import Path
from xml.sax.saxutils import escape

import mkdocs.plugins
from mkdocs.structure.files import File

USAGE_MSG = (
    "Usage: '!!swagger <filename>!!' or '!!swagger-http <url>!!'. "
    "File must either exist locally and be placed next to the .md that contains "
    "the swagger statement, or be an http(s) URL."
)

TEMPLATE = string.Template(
    """

<link type="text/css" rel="stylesheet" href="$swagger_lib_css">
<div id="swagger-ui">
</div>
<script src="$swagger_lib_js" charset="UTF-8"></script>
<script>
    const ui = SwaggerUIBundle({
    url: '$path',
    defaultModelsExpandDepth: -1,
    dom_id: '#swagger-ui',
    docExpansion: 'none',
    deepLinking: true,
    supportedSubmitMethods: [],
    })
</script>

"""
)

ERROR_TEMPLATE = string.Template("!! SWAGGER ERROR: $error !!")

# Used for JS. Runs locally on end-user. RFI / LFI not possible, no security risk.
# Restrict to local file.
TOKEN = re.compile(r"!!swagger(?: (?P<path>[^\\/\s><&:]+))?!!")

# HTTP(S) variant
TOKEN_HTTP = re.compile(r"!!swagger-http(?: (?P<path>https?://[^\s]+))?!!")


def swagger_lib(config) -> dict:
    """
    Provides the actual swagger library used
    """
    lib_swagger = {
        "css": "https://unpkg.com/swagger-ui-dist@3/swagger-ui.css",
        "js": "https://unpkg.com/swagger-ui-dist@3/swagger-ui-bundle.js",
    }

    extra_javascript = config.get("extra_javascript", [])
    extra_css = config.get("extra_css", [])
    for lib in extra_javascript:
        if os.path.basename(urllib.parse.urlparse(lib).path) == "swagger-ui-bundle.js":
            lib_swagger["js"] = lib
            break

    for css in extra_css:
        if os.path.basename(urllib.parse.urlparse(css).path) == "swagger-ui.css":
            lib_swagger["css"] = css
            break
    return lib_swagger


class SwaggerPlugin(mkdocs.plugins.BasePlugin):
    def on_page_markdown(self, markdown, page, config, files):
        is_http = False
        match = TOKEN.search(markdown)

        if match is None:
            match = TOKEN_HTTP.search(markdown)
            is_http = True

        if match is None:
            return markdown

        pre_token = markdown[: match.start()]
        post_token = markdown[match.end() :]

        def _error(message):
            return (
                pre_token
                + escape(ERROR_TEMPLATE.substitute(error=message))
                + post_token
            )

        path = match.group("path")

        if path is None:
            return _error(USAGE_MSG)

        if is_http:
            url = path
        else:
            try:
                api_file = Path(page.file.abs_src_path).with_name(path)
            except ValueError as exc:
                return _error(f"Invalid path. {exc.args[0]}")

            if not api_file.exists():
                return _error(f"File {path} not found.")

            src_dir = api_file.parent
            dest_dir = Path(page.file.abs_dest_path).parent

            new_file = File(api_file.name, src_dir, dest_dir, False)
            files.append(new_file)
            url = Path(new_file.abs_dest_path).name

        lib = swagger_lib(config)

        markdown = (
            pre_token
            + TEMPLATE.substitute(
                path=url, swagger_lib_js=lib["js"], swagger_lib_css=lib["css"]
            )
            + post_token
        )

        # If multiple swaggers exist.
        return self.on_page_markdown(markdown, page, config, files)
