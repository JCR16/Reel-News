// @vitest-environment jsdom

/*
 * Reel News - Frontend Unit Tests
 *
 * Developed by: Reel News team
 * Description: Tests story rendering and background image
 * fallback behavior in the React application.
 *
 * Team-developed tests:
 * - Verify stories returned by the API appear in the feed.
 * - Verify stories without images use the default background.
 * - Verify the default background remains in the CSS image stack.
 *
 * External libraries:
 * - Vitest: Test runner, assertions, and mocking.
 * - React Testing Library: Component rendering and queries.
 * - jest-dom: Additional DOM assertions.
 * - jsdom: Simulated browser environment.
 *
 * External code:
 * - No third-party test code copied or adapted
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import App from "./App";
import { getStories } from "./api/stories";

// Replace the real API function with a mock
vi.mock("./api/stories", () => ({
  getStories: vi.fn(),
}));

describe("Reel News Frontend", () => {
  it("displays a story returned by the API", async () => {

    // Simulate Django returning one story
    getStories.mockResolvedValue([
      {
        id: 1,
        headline: "Test Headline",
        summary: "This is a test summary.",
        status: "published",
        image: null,
      },
    ]);

    // Render the application
    render(<App />);

    // Verify the headline appears
    expect(
      await screen.findByRole("heading", {
        name: "[published] Test Headline",
      })
    ).toBeInTheDocument();

    // Verify the summary appears
    expect(
      screen.getByText("This is a test summary.")
    ).toBeInTheDocument();
  });


  it("uses the default background when a story has no image", async () => {

    // Simulate a story without an image
    getStories.mockResolvedValue([
      {
        id: 2,
        headline: "Story Without Image",
        summary: "Testing the default background.",
        status: "published",
        image: null,
      },
    ]);

    // Render the application
    const { container } = render(<App />);

    // Wait for the story to appear
    await screen.findByRole("heading", {
      name: "[published] Story Without Image",
    });

    // Find the story card
    const storyCard = container.querySelector(".article-card");

    // Verify the default newspaper image is applied
    expect(storyCard).toHaveStyle({
      backgroundImage: expect.stringContaining(
        "photo-1603484477859-abe6a73f9366"
      ),
    });
  });

  it("includes the default background when a custom image URL is provided", async () => {

    // Simulate a story without an image
    getStories.mockResolvedValue([
      {
        id: 2,
        headline: "Story Without Image",
        summary: "Testing the default background.",
        status: "published",
        image: "https://invalid-url.com/nonexistent-image.jpg", // Invalid image URL
      },
    ]);

    // Render the application
    const { container } = render(<App />);

    // Wait for the story to appear
    await screen.findByRole("heading", {
      name: "[published] Story Without Image",
    });

    // Find the story card
    const storyCard = container.querySelector(".article-card");

    // Verify the default newspaper image is applied
    expect(storyCard).toHaveStyle({
      backgroundImage: expect.stringContaining(
        "photo-1603484477859-abe6a73f9366"
      ),
    });
  });

});