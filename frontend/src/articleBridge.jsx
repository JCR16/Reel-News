/*
 * Reel News - Article Bridge
 *
 * Developed by: Reel News team
 * Description: Placeholder component for future article
 * explanation or navigation functionality.
 *
 * External libraries:
 * - React: Component rendering.
 * - React Router: Navigation using Link.
 *
 * External code:
 * - No third-party source code copied or adapted
 */

//import React from 'react'
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