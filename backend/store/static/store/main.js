const addLine = document.querySelector("#add-line");

if (addLine) {
    const lines = document.querySelector("#sale-lines");
    const total = document.querySelector("#id_items-TOTAL_FORMS");
    const template = document.querySelector("#empty-line");
    const max = Number(document.querySelector("#id_items-MAX_NUM_FORMS").value);

    function updateButton() {
        addLine.disabled = Number(total.value) >= max;
    }

    addLine.addEventListener("click", () => {
        const index = Number(total.value);
        if (index >= max) {
            return;
        }
        lines.insertAdjacentHTML("beforeend", template.innerHTML.replaceAll("__prefix__", index));
        total.value = index + 1;
        lines.lastElementChild.querySelector("select").focus();
        updateButton();
    });
    updateButton();
}

document.querySelector("[data-print]")?.addEventListener("click", () => window.print());
