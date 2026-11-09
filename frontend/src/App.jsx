/*
 * Reel News - Main Application
 *
 * Developed by: Reel News team
 * Description: Displays the news feed, retrieves stories from
 * the Django API, and handles story navigation.
 *
 * Team-developed functionality:
 * - Integration with the Django story API.
 * - Dynamic rendering of headlines, summaries, and story status.
 * - Story image handling and default background fallback.
 * - API retry logic and React state management.
 * - Integration of the news feed with React Router.
 *
 * External libraries:
 * - React: UI components, state management, and effects.
 * - React Router: Client-side navigation.
 *
 * External code/references:
 * - Button styling and scrolling behavior adapted from YouTube
 *   tutorials.
 *
 * External assets:
 * - Default newspaper image hosted on Unsplash.
 *   https://images.unsplash.com/photo-1603484477859-abe6a73f9366
 */

import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import ArticleBridge from './articleBridge'
import './App.css'
import { useEffect, useState } from "react";

//import { getHealth } from "./api/health";
import { getStories } from "./api/stories";

const defaultImage = "https://images.unsplash.com/photo-1603484477859-abe6a73f9366?w=1200";

function AppContent() {

  // State to hold the fetched stories
  const [stories, setStories] = useState([]); // setStories is set to be the function to update the stories state (this is the only definition)
  // Fetch stories when the component mounts
  useEffect(() => {
    let cancelled = false;
    let retryTimer;

    const fetchStories = async () => {
      try {
        const data = await getStories();

        if (!cancelled) {
          setStories(data);
        }
      } catch (error) {
        if (!cancelled) {
          console.error("Failed to load stories, retrying...", error);

          retryTimer = setTimeout(fetchStories, 5000);
        }
      }
    };

    fetchStories();

    return () => {
      cancelled = true;
      clearTimeout(retryTimer);
    };
  }, []);

  
  const handleCategoryClick = (e) => {
    e.preventDefault();

    window.open(
      "https://tracker.gg/valorant/profile/riot/SandToast%23Bread/overview?platform=pc&playlist=competitive&season=d816f426-48ea-f052-117f-9697a155b319",
      "_blank"
    );
  };

  return (
    <section id="center">
      <div className="feed">
        <div className="feed-loading">
          <p>Loading stories...</p>
        </div>
        {stories.map((story) => (
          <section
            className="article-card"
            key={story.id}
            style={{ //backgroundImage: `url(${article.image})` 
                backgroundImage: `url(${story.image || defaultImage}),
                url("${defaultImage}")` // stack background images in case story.image is invalid or missing, the default image will be used as a fallback
              }}
          >
            <div className="article-text">
              <h1>[{story.status}] {story.headline}</h1>
              <p>{story.summary}</p>
            </div>

            <div className="article-action">
              <Link to="/" onClick={handleCategoryClick}>
                <button type="button" style={{ cursor: "pointer", height: '33px' }}>
                  <span className="category">Sources</span>
                </button>
              </Link>
            </div>
          </section>
        ))}
      </div>
    </section>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppContent />} />
        <Route path="/some-path" element={<ArticleBridge />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;