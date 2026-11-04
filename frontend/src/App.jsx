import { useState } from 'react'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import ArticleBridge from './articleBridge'
import heroImg from './assets/hero.png'
import reactLogo from './assets/react.svg'
import viteLogo from './assets/vite.svg'
import './App.css'

const articles = [
  {
    id: 1,
    title: "Breaking News: Technology is Changing the World",
    description: "Discover the latest developments in technology and how they affect our everyday lives.",
    category: "Technology",
    image: "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1200"
  },
  {
    id: 2,
    title: "The Future of Artificial Intelligence",
    description: "A closer look at how AI is transforming industries around the world.",
    category: "Science",
    image: "https://images.unsplash.com/photo-1677442136019-21780ecad995?w=1200"
  },
  {
    id: 3,
    title: "Current Midterms Spark Conversation Across the Nation",
    description: "Stay informed on the latest political landscape.",
    category: "National News",
    image: "https://images.unsplash.com/photo-1529107386315-e1a2ed48a620?w=1200"
  }
];

function App() {
  const [count, setCount] = useState(0)

  return (
    <>
    <BrowserRouter>
    <Routes>
      <Route path="/" element={<App />} />
    </Routes>
      <section id="center">
        <div className="feed">
      {articles.map((article) => (
        <section
          className="article-card"
          key={article.id}
          style={{ backgroundImage: `url(${article.image})` }}
        >
          <div className="article-content">
            {/* Added a button with a link that is attached to each article category */}
            <Link to="/some-path">
              <button onClick = { () => window.open("https://tracker.gg/valorant/profile/riot/SandToast%23Bread/overview?platform=pc&playlist=competitive&season=d816f426-48ea-f052-117f-9697a155b319", "_blank")}>
                <span className="category">{article.category}</span>
              </button>
            </Link>
            <h1>{article.title}</h1>
            <p>{article.description}</p>
            {article.link}
          </div>
        </section>
      ))}

    </div>
        <div className="hero">
          <img src={heroImg} className="base" width="170" height="179" alt="" />
          <img src={reactLogo} className="framework" alt="React logo" />
          <img src={viteLogo} className="vite" alt="Vite logo" />
        </div>
        <div>
          <h1>Get started</h1>
          <p>
            Edit <code>src/App.jsx</code> and save to test <code>HMR</code>
          </p>
        </div>
        <button
          type="button"
          className="counter"
          onClick={() => setCount((count) => count + 1)}
          >
          Count is {count}
        </button>
      </section>

      <div className="ticks"></div>

      <section id="next-steps">
        <div id="docs">
          <svg className="icon" role="presentation" aria-hidden="true">
            <use href="/icons.svg#documentation-icon"></use>
          </svg>
          <h2>Documentation</h2>
          <p>Your questions, answered</p>
          <ul>
            <li>
              <a href="https://vite.dev/" target="_blank">
                <img className="logo" src={viteLogo} alt="" />
                Explore Vite
              </a>
            </li>
            <li>
              <a href="https://react.dev/" target="_blank">
                <img className="button-icon" src={reactLogo} alt="" />
                Learn more
              </a>
            </li>
          </ul>
        </div>
        <div id="social">
          <svg className="icon" role="presentation" aria-hidden="true">
            <use href="/icons.svg#social-icon"></use>
          </svg>
          <h2>Connect with us</h2>
          <p>Join the Vite community</p>
          <ul>
            <li>
              <a href="https://github.com/vitejs/vite" target="_blank">
                <svg
                  className="button-icon"
                  role="presentation"
                  aria-hidden="true"
                >
                  <use href="/icons.svg#github-icon"></use>
                </svg>
                GitHub
              </a>
            </li>
            <li>
              <a href="https://chat.vite.dev/" target="_blank">
                <svg
                  className="button-icon"
                  role="presentation"
                  aria-hidden="true"
                >
                  <use href="/icons.svg#discord-icon"></use>
                </svg>
                Discord
              </a>
            </li>
            <li>
              <a href="https://x.com/vite_js" target="_blank">
                <svg
                  className="button-icon"
                  role="presentation"
                  aria-hidden="true"
                >
                  <use href="/icons.svg#x-icon"></use>
                </svg>
                X.com
              </a>
            </li>
            <li>
              <a href="https://bsky.app/profile/vite.dev" target="_blank">
                <svg
                  className="button-icon"
                  role="presentation"
                  aria-hidden="true"
                >
                  <use href="/icons.svg#bluesky-icon"></use>
                </svg>
                Bluesky
              </a>
            </li>
          </ul>
        </div>
      </section>

      <div className="ticks"></div>
      <section id="spacer"></section>
      </BrowserRouter>
    </>
  );
}

export default App
