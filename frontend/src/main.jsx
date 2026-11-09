/*
 * Reel News - React Application Entry Point
 *
 * External code:
 * - Generated from the standard Vite React project template.
 * - Uses React and React DOM to initialize the application.
 *
 * Team modifications:
 * - None. Original Vite-generated implementation retained.
 */

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
