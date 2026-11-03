export async function getHealth() {
  const response = await fetch("http://localhost:8000/api/health/");

  if (!response.ok) {
    throw new Error("Failed to fetch API health");
  }
  return response.json();
}