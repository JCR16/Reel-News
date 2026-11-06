import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import ArticleBridge from './articleBridge'
import './App.css'

import { getHealth } from "./api/health";

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

function AppContent() {
  
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
        {articles.map((article) => (
          <section
            className="article-card"
            key={article.id}
            style={{ backgroundImage: `url(${article.image})` }}
          >
            <div className="article-text">
              <h1>{article.title}</h1>
              <p>{article.description}</p>
            </div>

            <div className="article-action">
              <Link to="/" onClick={handleCategoryClick}>
                <button type="button" style={{ cursor: "pointer", height: '33px', backgroundColor: 'transparent'}}>
                  <span className="category">{article.category}</span>
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