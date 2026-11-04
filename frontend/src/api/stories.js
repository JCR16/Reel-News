const API_BASE_URL =
    import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function getStories() {
    const response = await fetch(`${API_BASE_URL}/api/stories/`);

    if (!response.ok) {
        throw new Error("Failed to fetch stories");
    }

    return response.json();
}