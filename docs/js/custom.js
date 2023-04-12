function setupTermynal() {
    document.querySelectorAll(".use-termynal").forEach(node => {
        node.style.display = "block";
        new Termynal(node, {
            lineDelay: 500
        });
    });
    const progressLiteralStart = "---> 100%";
    const promptLiteralStart = "$ ";
    const pythonPromptLiteralStart = ">>> ";
    const pythonPromptBlockStart = "... ";
    const termynalActivateClass = "termy";
    let termynals = [];

    function createTermynals() {
        document
            .querySelectorAll(`.${termynalActivateClass} .highlight`)
            .forEach(node => {
                const text = node.textContent;
                const lines = text.split("\n");
                const useLines = [];
                let buffer = [];
                function saveBuffer() {
                    if (buffer.length) {
                        let isBlankSpace = true;
                        buffer.forEach(line => {
                            if (line) {
                                isBlankSpace = false;
                            }
                        });
                        dataValue = {};
                        if (isBlankSpace) {
                            dataValue["delay"] = 0;
                        }
                        if (buffer[buffer.length - 1] === "") {
                            // A last single <br> won't have effect
                            // so put an additional one
                            buffer.push("");
                        }
                        const bufferValue = buffer.join("<br>");
                        dataValue["value"] = bufferValue;
                        useLines.push(dataValue);
                        buffer = [];
                    }
                }
                for (let line of lines) {
                    if (line === progressLiteralStart) {
                        saveBuffer();
                        useLines.push({
                            type: "progress"
                        });
                    } else if (line.startsWith(promptLiteralStart)) {
                        saveBuffer();
                        const value = line.replace(promptLiteralStart, "").trimEnd();
                        useLines.push({
                            type: "input",
                            value: value
                        });
                    } else if (line.startsWith("// ")) {
                        saveBuffer();
                        const value = "💬 " + line.replace("// ", "").trimEnd();
                        useLines.push({
                            value: value,
                            class: "termynal-comment",
                            delay: 0
                        });
                    } else if (line.startsWith(pythonPromptLiteralStart)) {
                        saveBuffer();
                        const value = line.replace(pythonPromptLiteralStart, "").trimEnd();
                        useLines.push({
                            type: "input",
                            value: value,
                            prompt: ">>>"
                        });
                    } else if (line.startsWith(pythonPromptBlockStart)) {
                        saveBuffer();
                        // replace 4 space indents with 3 no-break space chars
                        // termynal will add an additional prefix space so this will render as expected
                        const value = line.replace(pythonPromptBlockStart, "").replace("    ", "\xa0\xa0\xa0").trimEnd();
                        useLines.push({
                            type: "input",
                            value: value,
                            prompt: "..."
                        });
                    } else {
                        buffer.push(line);
                    }
                }
                saveBuffer();
                const div = document.createElement("div");
                node.replaceWith(div);
                const termynal = new Termynal(div, {
                    lineData: useLines,
                    noInit: true,
                    lineDelay: 250
                });
                termynals.push(termynal);
            });
    }

    function loadVisibleTermynals() {
        termynals = termynals.filter(termynal => {
            if (termynal.container.getBoundingClientRect().top - innerHeight <= 0) {
                termynal.init();
                return false;
            }
            return true;
        });
    }
    window.addEventListener("scroll", loadVisibleTermynals);
    createTermynals();
    loadVisibleTermynals();
}

/**
 * This function is enhances the 'copy to clipboard' buttons on terminal blocks 
 * by removing leading $ signs. This ensures users can copy and paste the
 * commands into their terminal without having to manually remove the $ signs.
 */
function enhanceCopyButtons() {
    // Wait until the DOM is loaded before looking up the buttons
    document.addEventListener("DOMContentLoaded", function() {
        var buttons = document.querySelectorAll(
            ".terminal pre[id^='__code_'] button.md-code__button");
        buttons.forEach(function(button) {
            // Check if the button's "data-clipboard-target" attribute is already
            // a cleaned textarea - if so, no need to clean it again.
            if (!button.getAttribute("data-clipboard-target").startsWith("#__cleaned")) {
                // Next, add event listeners to the button to clean the code block
                // before the 'click' event handler copies the code to the clipboard.

                // On desktop devices, clean the code block when the user
                // hovers over the button.
                button.addEventListener("mouseenter", copyCleaner);

                // On mobile devices, clean the code block when the user
                // taps on the button. This works because the 'click' event
                // is fired after the 'touchstart' event.
                button.addEventListener("touchstart", copyCleaner);

                function copyCleaner() {
                    // Look up the code block referenced by the button's 
                    // "data-clipboard-target" attribute.
                    var codeBlockSelector = button.getAttribute("data-clipboard-target");

                    // return early if we've already cleaned this code block
                    if (codeBlockSelector.startsWith("#__cleaned")) { return; }
                    var codeBlock = document.querySelector(codeBlockSelector);

                    // clean the code block by removing leading $ signs and trim whitespace
                    var cleanedCode = codeBlock.innerText.replace(/^\$\s/gm, "").trim();
                    var cleanedCodeId = "__cleaned_" + codeBlockSelector.replace('#','').split(" ")[0];
                    var cleanedCodeBlock = document.getElementById(cleanedCodeId);

                    // if the cleaned code block doesn't exist, create it and add it to the DOM
                    if (cleanedCodeBlock == null) {
                        cleanedCodeBlock = document.createElement("code");
                        cleanedCodeBlock.id = cleanedCodeId;
                        cleanedCodeBlock.innerHTML = cleanedCode;
                        
                        cleanedCodeBlock.style.display = "none";
                        document.body.appendChild(cleanedCodeBlock);
                    }
                    button.setAttribute("data-clipboard-target", "#" + cleanedCodeId);
                }
            }
        });
    });
} 

async function main() {
    setupTermynal();
    enhanceCopyButtons();
}

main()