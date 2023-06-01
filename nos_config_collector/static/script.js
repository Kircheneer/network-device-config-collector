const configTextarea = document.getElementById("configTextarea")

async function anonymize_configuration() {
    const sensitiveWordsTextArea = document.getElementById("sensitiveWordsTextarea")
    const anonymizeButton = document.getElementById("anonymizeButton")
    const submitButton = document.getElementById("submitButton")

    const configuration = configTextarea.value
    const sensitive_words = sensitiveWordsTextArea.value.split("\n")
    const data = { content: configuration, sensitive_words: sensitive_words }
    const response = await fetch("/configurations/anonymize/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(data)
    })
    const result = await response.json();
    configTextarea.value = result.content;

    // Disable all involved components to signal to the user that they aren't relevant anymore.
    // Note that we allow editing of the configuration still to allow the user to make some final tweaks.
    for (form_component of [sensitiveWordsTextArea, anonymizeButton]) {
        switch(form_component.nodeName) {
            case "TEXTAREA":
                form_component.readOnly = "true";
                break;
            case "BUTTON":
                form_component.disabled = "true";
                form_component.classList.remove("btn-primary");
                form_component.classList.add("btn-outline-primary");
                break;
        }
    }

    // Activate submit button
    submitButton.removeAttribute("disabled");
    submitButton.classList.remove("btn-outline-primary");
    submitButton.classList.add("btn-primary");
}

async function submit_configuration() {
    const modalElement = document.getElementById("finishedModal");
    const modalBody = document.getElementById("finishedModalBody");
    const modal = new bootstrap.Modal(modalElement);
    modal.show();

    const name = document.getElementById("nameInput").value;
    const email = document.getElementById("githubMailInput").value;
    const nos = document.getElementById("nosSelect").value;
    const configuration = configTextarea.value;
    const data = { content: configuration, author: name, email: email, nos: nos }
    const response = await fetch("/configurations/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(data)
    })
    const responseAsJSON = await response.json();
    if (responseAsJSON.pr_link) {
        modalBody.innerHTML = `<p><a href="${responseAsJSON.pr_link}">PR</a> successfully submitted.</p>`;
    } else {
        modalBody.innerHTML = `<p>Encountered error: ${responseAsJSON.error}</p>`;
        console.log(responseAsJSON.error);
    }
}