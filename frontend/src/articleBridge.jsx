import React from 'react'
import { Link } from 'react-router-dom'

//Lowkey just ignore all of this for now
const ArticleBridge = () => {
  return (
    <div>
      <h1>Explanation</h1>
      <Link to="/some-path">
            <button>
              Link to Explanation
            </button>
          </Link>
    </div>
  )
}

export default ArticleBridge