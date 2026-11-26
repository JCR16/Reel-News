/*
 * Reel News - Bookmark Interaction
 *
 * Developed by: Reel News team
 * Description: Handles bookmark toggling through Django
 * endpoints without requiring a page refresh.
 */

document.addEventListener("DOMContentLoaded", () => {
    // Retrieve all bookmark buttons on the page.
    const buttons = document.querySelectorAll(".bookmark-button");

    // No bookmark functionality is needed if no buttons exist.
    if (buttons.length === 0) {
        return;
    }

    // Retrieve the CSRF token from the existing logout form.
    const csrfToken = document.querySelector(
        'input[name="csrfmiddlewaretoken"]'
    ).value;

    // Attach a click handler to each bookmark button.
    buttons.forEach((button) => {
        button.addEventListener("click", async () => {

            // Determine whether the story is currently bookmarked.
            const isBookmarked =
                button.getAttribute("aria-pressed") === "true";

            // Select the appropriate backend endpoint.
            const url = isBookmarked
                ? button.dataset.removeUrl
                : button.dataset.addUrl;

            // Prevent repeated clicks while the request is processing.
            button.disabled = true;

            try {
                // Send the bookmark request to Django.
                const response = await fetch(url, {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": csrfToken,
                        "Accept": "application/json",
                    },
                    credentials: "same-origin",
                });

                // Ensure the backend successfully processed the request.
                if (!response.ok) {
                    throw new Error(`Request failed: ${response.status}`);
                }

                const data = await response.json();

                // Verify that the response contains a valid bookmark state.
                if (typeof data.bookmarked !== "boolean") {
                    throw new Error("Invalid bookmark response.");
                }

                // Update the button using the confirmed backend state.
                // CSS automatically updates the icon's appearance.
                button.setAttribute("aria-pressed", String(data.bookmarked));

            } catch (error) {
                // Preserve the previous bookmark state if the request fails.
                console.error("Bookmark request failed:", error);
                alert("Unable to update bookmark. Please try again.");

            } finally {
                // Re-enable the button regardless of the request outcome.
                button.disabled = false;
            }
        });
    });
});