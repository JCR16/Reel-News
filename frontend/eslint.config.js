/*
 * Reel News - ESLint Configuration
 *
 * External code:
 * - Generated from the standard Vite React project template.
 * - Uses ESLint's recommended JavaScript rules and the
 *   React Hooks and React Refresh plugins.
 *
 * Team modifications:
 * - None. Original template configuration retained.
 */

import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
  },
])
