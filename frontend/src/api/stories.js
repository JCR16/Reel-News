/*
 * Reel News - Stories API Helper
 *
 * Developed by: Reel News team
 * Description: Retrieves news stories from the Django REST API
 * and returns the response as JSON.
 *
 * Team-developed functionality:
 * - Configurable backend URL using Vite environment variables.
 * - HTTP request to the Reel News stories endpoint.
 * - Error handling for unsuccessful HTTP responses.
 *
 * External technologies:
 * - JavaScript Fetch API: HTTP requests.
 * - Vite: Environment variable configuration.
 *
 * External code:
 * - No third-party source code copied or adapted
 */

const API_BASE_URL =
    import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function getStories() {
    const response = await fetch(`${API_BASE_URL}/api/stories/`);

    if (!response.ok) {
        throw new Error("Failed to fetch stories");
    }

    return response.json();
}