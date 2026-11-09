/*
 * Reel News - API Health Check Helper
 *
 * Developed by: Reel News team
 * Description: Sends a request to the Django health-check
 * endpoint to verify that the backend is responding.
 *
 * Team-developed functionality:
 * - Configurable backend URL using Vite environment variables.
 * - HTTP request to the Reel News health-check endpoint.
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

export async function getHealth() {
    const response = await fetch(`${API_BASE_URL}/api/health/`);

    if (!response.ok) {
        throw new Error("Failed to fetch API health");
    }

    return response.json();
}